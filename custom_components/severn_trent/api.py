"""API client for Severn Trent Water."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .const import (
    API_URL,
    SEND_MAGIC_LINK_MUTATION,
    EXCHANGE_TOKEN_MUTATION,
    ACCOUNT_LIST_QUERY,
    METER_IDENTIFIERS_QUERY,
    METER_READINGS_QUERY,
    SMART_METER_READINGS_QUERY,
)

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""

    pass


class SevernTrentAPI:
    """API client for Severn Trent Water."""

    def __init__(
        self,
        email: str,
        account_number: str = None,
        market_supply_point_id: str = None,
        device_id: str = None,
        refresh_token: str = None,
        refresh_token_expires_at: int = None,
    ):
        """Initialize the API client."""
        self.email = email
        self.account_number = account_number
        self.market_supply_point_id = market_supply_point_id
        self.device_id = device_id
        self.token = None
        self.refresh_token = refresh_token
        self.token_expires_at = 0
        self.refresh_token_expires_at = refresh_token_expires_at or 0
        self.meter_identifiers_fetched = False

    @staticmethod
    async def send_magic_link_email(email: str) -> bool:
        """Send magic link email to user."""
        try:
            _LOGGER.info("Sending magic link email to %s", email)

            headers = {
                "Content-Type": "application/json",
                "Origin": "https://my-account.stwater.co.uk",
                "Referer": "https://my-account.stwater.co.uk/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    json={
                        "query": SEND_MAGIC_LINK_MUTATION,
                        "variables": {"input": {"email": email}},
                    },
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if "data" in data and "sendOneTimeLoginEmail" in data["data"]:
                        status = data["data"]["sendOneTimeLoginEmail"].get("status")
                        if status == "OK":
                            _LOGGER.info("Magic link email sent successfully")
                            return True

                    _LOGGER.error("Failed to send magic link email. Response: %s", data)
                    return False
        except Exception as e:
            _LOGGER.error("Error sending magic link email: %s", e, exc_info=True)
            return False

    @staticmethod
    def extract_token_from_url(url: str) -> str | None:
        """Extract 64-char hex token from magic link URL."""
        patterns = [
            r"https://my-account\.stwater\.co\.uk/\?key=([a-f0-9]{64})",
            r"https://my-account\.stwater\.co\.uk/sign-in/([a-f0-9]{64})",
            r"^([a-f0-9]{64})$",  # Allow direct token paste
        ]

        url = url.strip()
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                token = match.group(1)
                _LOGGER.debug("Extracted token: %s...", token[:16])
                return token

        _LOGGER.error("Could not extract token from URL: %s", url[:50])
        return None

    async def exchange_token_for_jwt(self, magic_token: str) -> bool:
        """Exchange magic link token for JWT and refresh token."""
        try:
            _LOGGER.info("Exchanging magic link token for JWT")

            headers = {
                "Content-Type": "application/json",
                "Origin": "https://my-account.stwater.co.uk",
                "Referer": "https://my-account.stwater.co.uk/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    json={
                        "query": EXCHANGE_TOKEN_MUTATION,
                        "variables": {"input": {"refreshToken": magic_token}},
                        "operationName": "LoginWithMagicLinkToken",
                    },
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if "errors" in data:
                        _LOGGER.error("GraphQL errors exchanging token: %s", data["errors"])
                        return False

                    if "data" in data and "obtainKrakenToken" in data["data"]:
                        token_data = data["data"]["obtainKrakenToken"]
                        self.token = token_data["token"]
                        self.refresh_token = token_data["refreshToken"]

                        # JWT expires in 900 seconds (15 min), refresh in ~30 min
                        # Set JWT expiry with 60 second buffer for safety
                        self.token_expires_at = time.time() + 840  # 14 minutes

                        # Refresh token expiry from API (Unix timestamp)
                        refresh_expires_in = token_data.get("refreshExpiresIn")
                        if refresh_expires_in:
                            self.refresh_token_expires_at = refresh_expires_in
                        else:
                            # Fallback: ~30 minutes from now
                            self.refresh_token_expires_at = int(time.time() + 1800)

                        _LOGGER.info(
                            "Successfully obtained JWT. Token starts with: %s...",
                            self.token[:30],
                        )
                        _LOGGER.debug("JWT expires at: %s", self.token_expires_at)
                        _LOGGER.debug(
                            "Refresh token expires at: %s", self.refresh_token_expires_at
                        )
                        return True
                    else:
                        _LOGGER.error("Failed to exchange token. Response: %s", data)
                        return False
        except Exception as e:
            _LOGGER.error("Error exchanging token: %s", e, exc_info=True)
            return False

    async def refresh_jwt_token(self) -> bool:
        """Refresh JWT using the refresh token."""
        if not self.refresh_token:
            _LOGGER.error("No refresh token available")
            raise AuthenticationError("No refresh token available")

        # Check if refresh token has expired
        if time.time() >= self.refresh_token_expires_at:
            _LOGGER.error("Refresh token has expired")
            raise AuthenticationError("Refresh token expired")

        try:
            _LOGGER.info("Refreshing JWT token")

            headers = {
                "Content-Type": "application/json",
                "Origin": "https://my-account.stwater.co.uk",
                "Referer": "https://my-account.stwater.co.uk/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    json={
                        "query": EXCHANGE_TOKEN_MUTATION,
                        "variables": {"input": {"refreshToken": self.refresh_token}},
                        "operationName": "LoginWithMagicLinkToken",
                    },
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if "errors" in data:
                        _LOGGER.error("GraphQL errors refreshing token: %s", data["errors"])
                        raise AuthenticationError("Failed to refresh token")

                    if "data" in data and "obtainKrakenToken" in data["data"]:
                        token_data = data["data"]["obtainKrakenToken"]
                        self.token = token_data["token"]

                        # Update JWT expiry (14 minutes with buffer)
                        self.token_expires_at = time.time() + 840

                        _LOGGER.info("Successfully refreshed JWT token")
                        _LOGGER.debug("New JWT expires at: %s", self.token_expires_at)
                        return True
                    else:
                        _LOGGER.error("Failed to refresh token. Response: %s", data)
                        raise AuthenticationError("Failed to refresh token")
        except aiohttp.ClientError as e:
            _LOGGER.error("Error refreshing token: %s", e, exc_info=True)
            raise AuthenticationError(f"Failed to refresh token: {e}") from e

    async def _ensure_valid_token(self):
        """Ensure we have a valid token, refreshing if necessary."""
        # Check if JWT has expired
        if time.time() >= self.token_expires_at:
            _LOGGER.info("JWT token expired, refreshing")
            await self.refresh_jwt_token()

    async def fetch_account_numbers(self) -> list[str]:
        """Fetch list of account numbers for the authenticated user."""
        try:
            await self._ensure_valid_token()
            _LOGGER.info("Fetching account numbers")

            headers = {
                "Authorization": f"JWT {self.token}",
                "Content-Type": "application/json",
                "Origin": "https://my-account.stwater.co.uk",
                "Referer": "https://my-account.stwater.co.uk/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    headers=headers,
                    json={
                        "query": ACCOUNT_LIST_QUERY,
                        "operationName": "AccountNumberList",
                    },
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if "errors" in data:
                        _LOGGER.error(
                            "GraphQL errors fetching account numbers: %s", data["errors"]
                        )
                        return []

                    if "data" not in data or "viewer" not in data["data"]:
                        _LOGGER.error("Unexpected response when fetching account numbers")
                        return []

                    accounts = data["data"]["viewer"].get("accounts", [])
                    account_numbers = [acc["number"] for acc in accounts]

                    _LOGGER.info("Found %d account(s)", len(account_numbers))
                    return account_numbers

        except Exception as e:
            _LOGGER.error("Error fetching account numbers: %s", e, exc_info=True)
            return []

    async def _fetch_meter_identifiers(self) -> bool:
        """Fetch meter identifiers (device ID and market supply point ID)."""
        if self.meter_identifiers_fetched:
            return True

        if self.market_supply_point_id and self.device_id:
            _LOGGER.debug("Meter identifiers already provided")
            self.meter_identifiers_fetched = True
            return True

        try:
            await self._ensure_valid_token()
            _LOGGER.info("Fetching meter identifiers automatically")

            headers = {
                "Authorization": f"JWT {self.token}",
                "Content-Type": "application/json",
                "Origin": "https://my-account.stwater.co.uk",
                "Referer": "https://my-account.stwater.co.uk/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    headers=headers,
                    json={
                        "query": METER_IDENTIFIERS_QUERY,
                        "variables": {"accountNumber": self.account_number},
                        "operationName": "GetMeterIdentifiers",
                    },
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if "errors" in data:
                        _LOGGER.error(
                            "GraphQL errors fetching meter identifiers: %s", data["errors"]
                        )
                        return False

                    if "data" not in data or "account" not in data["data"]:
                        _LOGGER.error("Unexpected response when fetching meter identifiers")
                        return False

                    if data["data"]["account"] is None:
                        _LOGGER.error("Account not found when fetching meter identifiers")
                        return False

                    properties = data["data"]["account"].get("properties", [])
                    if not properties or not properties[0].get("activeWaterMeters"):
                        _LOGGER.error("No active water meters found")
                        return False

                    meters = properties[0]["activeWaterMeters"]
                    if not meters:
                        _LOGGER.error("Empty meters list")
                        return False

                    meter = meters[0]
                    self.market_supply_point_id = meter.get("meterPointReference")
                    self.device_id = meter.get("serialNumber")

                    if not self.market_supply_point_id or not self.device_id:
                        _LOGGER.error("Failed to extract meter identifiers from response")
                        return False

                    _LOGGER.info(
                        "Successfully discovered meter identifiers: MSPID=%s, DeviceID=%s",
                        self.market_supply_point_id,
                        self.device_id,
                    )
                    self.meter_identifiers_fetched = True
                    return True

        except Exception as e:
            _LOGGER.error("Error fetching meter identifiers: %s", e, exc_info=True)
            return False

    async def get_meter_readings(self) -> dict[str, Any]:
        """Get meter readings from the API."""
        # Ensure token is valid (will refresh if needed)
        await self._ensure_valid_token()

        # Fetch meter identifiers if not already done
        if not await self._fetch_meter_identifiers():
            _LOGGER.error("Failed to fetch meter identifiers")
            return {}

        if not self.token:
            _LOGGER.error("No token available!")
            return {}

        _LOGGER.debug("Using token: %s... (length: %d)", self.token[:30], len(self.token))

        if not self.market_supply_point_id or not self.device_id:
            _LOGGER.error("Missing marketSupplyPointId or deviceId")
            return {}

        try:
            # Get yesterday's data (since today's data isn't available yet)
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=7)  # Get last 7 days for daily data

            _LOGGER.info("Fetching daily readings from %s to %s", start_date, end_date)

            headers = {
                "Authorization": f"JWT {self.token}",
                "Content-Type": "application/json",
                "Origin": "https://my-account.stwater.co.uk",
                "Referer": "https://my-account.stwater.co.uk/",
            }

            async with aiohttp.ClientSession() as session:
                # Fetch daily readings (last 7 days)
                async with session.post(
                    API_URL,
                    headers=headers,
                    json={
                        "query": SMART_METER_READINGS_QUERY,
                        "variables": {
                            "accountNumber": self.account_number,
                            "startAt": start_date.isoformat() + "Z",
                            "endAt": end_date.isoformat() + "Z",
                            "utilityFilters": [
                                {
                                    "waterFilters": {
                                        "readingFrequencyType": "HOUR_INTERVAL",
                                        "marketSupplyPointId": self.market_supply_point_id,
                                        "deviceId": self.device_id,
                                    }
                                }
                            ],
                        },
                        "operationName": "SmartMeterReadings",
                    },
                ) as daily_response:
                    daily_response.raise_for_status()
                    daily_data = await daily_response.json()

                    if "errors" in daily_data:
                        _LOGGER.error(
                            "GraphQL errors fetching daily data: %s", daily_data["errors"]
                        )
                        return {}

                # Fetch monthly readings (last 12 months for estimation calculations)
                monthly_start = end_date - timedelta(days=365)
                _LOGGER.info("Fetching monthly readings from %s to %s", monthly_start, end_date)

                async with session.post(
                    API_URL,
                    headers=headers,
                    json={
                        "query": SMART_METER_READINGS_QUERY,
                        "variables": {
                            "accountNumber": self.account_number,
                            "startAt": monthly_start.isoformat() + "Z",
                            "endAt": end_date.isoformat() + "Z",
                            "utilityFilters": [
                                {
                                    "waterFilters": {
                                        "readingFrequencyType": "MONTH_INTERVAL",
                                        "marketSupplyPointId": self.market_supply_point_id,
                                        "deviceId": self.device_id,
                                    }
                                }
                            ],
                        },
                        "operationName": "SmartMeterReadings",
                    },
                ) as monthly_response:
                    monthly_response.raise_for_status()
                    monthly_data = await monthly_response.json()

                    if "errors" in monthly_data:
                        _LOGGER.error(
                            "GraphQL errors fetching monthly data: %s", monthly_data["errors"]
                        )
                        # Continue with just daily data
                        monthly_measurements = []
                    else:
                        monthly_properties = (
                            monthly_data.get("data", {}).get("account", {}).get("properties", [])
                        )
                        if monthly_properties:
                            monthly_measurements = (
                                monthly_properties[0].get("measurements", {}).get("edges", [])
                            )
                        else:
                            monthly_measurements = []

            # Process daily data
            if "data" not in daily_data or "account" not in daily_data["data"]:
                _LOGGER.error("Unexpected API response structure")
                return {}

            if daily_data["data"]["account"] is None:
                _LOGGER.error("Account is None in response")
                return {}

            properties = daily_data["data"]["account"].get("properties", [])
            if not properties:
                _LOGGER.warning("No properties in response")
                return {}

            measurements = properties[0].get("measurements", {}).get("edges", [])
            _LOGGER.info("Found %d hourly measurements", len(measurements))

            if not measurements:
                _LOGGER.warning("No measurements found")
                return {}

            # Group hourly measurements by day
            daily_totals = {}
            for measurement in measurements:
                node = measurement["node"]
                try:
                    value = float(node["value"])
                except (ValueError, TypeError):
                    value = 0.0

                start_at = node.get("startAt")

                if start_at:
                    date_str = start_at.split("T")[0]
                    if date_str not in daily_totals:
                        daily_totals[date_str] = 0
                    daily_totals[date_str] += value

            _LOGGER.debug("Daily totals: %s", daily_totals)

            # Sort days by date (most recent first)
            sorted_days = sorted(daily_totals.items(), key=lambda x: x[0], reverse=True)

            if not sorted_days:
                _LOGGER.warning("No daily totals calculated")
                return {}

            # Get yesterday's total (most recent complete day)
            yesterday_date, yesterday_total = sorted_days[0]

            _LOGGER.info("Yesterday (%s): %s m³", yesterday_date, yesterday_total)

            # Calculate running total and build readings list
            all_readings = []
            total_usage = 0

            for date_str, daily_total in sorted_days:
                all_readings.append(
                    {"value": round(daily_total, 3), "date": date_str, "unit": "m³"}
                )
                total_usage += daily_total

            # Calculate average daily usage
            num_days = len(all_readings)
            avg_daily_usage = total_usage / num_days if num_days > 0 else 0

            # Process monthly data
            monthly_readings = []
            for measurement in monthly_measurements:
                node = measurement["node"]
                try:
                    value = float(node["value"])
                except (ValueError, TypeError):
                    value = 0.0

                start_at = node.get("startAt")

                if start_at:
                    # Extract year-month
                    date_str = start_at.split("T")[0]
                    monthly_readings.append(
                        {"value": round(value, 3), "start_date": date_str, "unit": "m³"}
                    )

            _LOGGER.info("Found %d monthly readings", len(monthly_readings))

            return {
                "meter_id": f"{self.market_supply_point_id}_{self.device_id}",
                "yesterday_usage": round(yesterday_total, 3),
                "yesterday_date": yesterday_date,
                "daily_average": round(avg_daily_usage, 3),
                "total_7day_usage": round(total_usage, 3),
                "unit": "m³",
                "all_readings": all_readings,
                "monthly_readings": monthly_readings,
            }

        except aiohttp.ClientError as e:
            _LOGGER.error("HTTP error fetching meter readings: %s", e, exc_info=True)
            return {}
        except Exception as e:
            _LOGGER.error("Error fetching meter readings: %s", e, exc_info=True)
            return {}

    async def get_manual_meter_readings(self) -> dict[str, Any]:
        """Get manual meter readings from the API."""
        await self._ensure_valid_token()

        try:
            # Get readings from the past year
            active_from = (datetime.now() - timedelta(days=365)).isoformat() + "Z"

            _LOGGER.debug("Fetching manual meter readings")

            headers = {
                "Authorization": f"JWT {self.token}",
                "Content-Type": "application/json",
                "Origin": "https://my-account.stwater.co.uk",
                "Referer": "https://my-account.stwater.co.uk/",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL,
                    headers=headers,
                    json={
                        "query": METER_READINGS_QUERY,
                        "variables": {
                            "accountNumber": self.account_number,
                            "activeFrom": active_from,
                        },
                        "operationName": "MeterReadings",
                    },
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if "errors" in data:
                        _LOGGER.error(
                            "GraphQL errors fetching manual readings: %s", data["errors"]
                        )
                        return {}

                    if "data" not in data or "account" not in data["data"]:
                        _LOGGER.error("Unexpected API response for manual readings")
                        return {}

                    if data["data"]["account"] is None:
                        _LOGGER.error("Account not found for manual readings")
                        return {}

                    properties = data["data"]["account"].get("properties", [])
                    if not properties or not properties[0].get("activeWaterMeters"):
                        _LOGGER.warning("No meters found for manual readings")
                        return {}

                    meter = properties[0]["activeWaterMeters"][0]
                    readings = meter["readings"]["edges"]

                    if not readings:
                        _LOGGER.warning("No manual readings found")
                        return {}

                    # Most recent reading first
                    latest = readings[0]["node"]
                    latest_value = float(latest["valueCubicMetres"])
                    latest_date = latest["readingDate"]
                    latest_source = latest["source"]

                    # Calculate usage since previous reading
                    usage_since_last = None
                    days_since_last = None
                    avg_daily_usage = None
                    previous_value = None
                    previous_date = None

                    if len(readings) >= 2:
                        previous = readings[1]["node"]
                        previous_value = float(previous["valueCubicMetres"])
                        previous_date = previous["readingDate"]

                        usage_since_last = latest_value - previous_value

                        latest_dt = datetime.fromisoformat(latest_date)
                        previous_dt = datetime.fromisoformat(previous_date)
                        days_since_last = (latest_dt - previous_dt).days

                        if days_since_last > 0:
                            avg_daily_usage = usage_since_last / days_since_last

                    _LOGGER.info("Latest manual reading: %s m³ on %s", latest_value, latest_date)

                    return {
                        "meter_id": meter["id"],
                        "latest_reading": latest_value,
                        "reading_date": latest_date,
                        "reading_source": latest_source,
                        "previous_reading": previous_value,
                        "previous_date": previous_date,
                        "usage_since_last": (
                            round(usage_since_last, 3) if usage_since_last else None
                        ),
                        "days_since_last": days_since_last,
                        "avg_daily_usage": (
                            round(avg_daily_usage, 3) if avg_daily_usage else None
                        ),
                        "all_readings": [
                            {
                                "value": float(r["node"]["valueCubicMetres"]),
                                "date": r["node"]["readingDate"],
                                "source": r["node"]["source"],
                            }
                            for r in readings
                        ],
                    }

        except Exception as e:
            _LOGGER.error("Error fetching manual meter readings: %s", e, exc_info=True)
            return {}

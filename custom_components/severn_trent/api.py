"""API client for Severn Trent Water."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import requests

from .const import (
    API_KEY_MUTATION,
    API_URL,
    AUTH_MUTATION,
    ACCOUNT_LIST_QUERY,
    METER_IDENTIFIERS_QUERY,
    METER_READINGS_QUERY,
    SMART_METER_READINGS_QUERY,
)

_LOGGER = logging.getLogger(__name__)

class SevernTrentAPI:
    """API client for Severn Trent Water."""
    
    def __init__(
        self,
        api_key: str | None,
        account_number: str | None = None,
        market_supply_point_id: str | None = None,
        device_id: str | None = None,
    ):
        """Initialize the API client."""
        self.api_key = api_key
        self.account_number = account_number
        self.market_supply_point_id = market_supply_point_id
        self.device_id = device_id
        self.token = None
        self.refresh_token = None
        self.token_expires_at = 0
        self.session = requests.Session()
        self.meter_identifiers_fetched = False

    @staticmethod
    def _normalize_browser_token(browser_token: str) -> str:
        token = browser_token.strip()
        if token.lower().startswith("bearer "):
            return token[7:].strip()
        return token

    @staticmethod
    def generate_api_key(browser_token: str) -> str | None:
        """Exchange a temporary browser token for a long-lived API key."""
        token = SevernTrentAPI._normalize_browser_token(browser_token)
        if not token:
            return None

        try:
            session = requests.Session()
            response = session.post(
                API_URL,
                json={"query": API_KEY_MUTATION},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": token,
                },
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                _LOGGER.error("API key generation errors: %s", data["errors"])
                return None

            key = data.get("data", {}).get("regenerateSecretKey", {}).get("key")
            if not key:
                _LOGGER.error("API key missing in response")
                return None

            return key
        except Exception as e:
            _LOGGER.error("API key generation error: %s", e, exc_info=True)
            return None
    
    def authenticate(self) -> bool:
        """Authenticate with the API and obtain JWT token."""
        if not self.api_key:
            _LOGGER.error("Missing API key; cannot authenticate")
            return False

        try:
            _LOGGER.info("Attempting API key authentication")
            _LOGGER.debug("Account number: %s", self.account_number)
            
            response = self.session.post(
                API_URL,
                json={
                    "query": AUTH_MUTATION,
                    "variables": {
                        "input": {
                            "APIKey": self.api_key
                        }
                    },
                    "operationName": "ObtainKrakenToken"
                }
            )
            _LOGGER.debug("Auth response status: %s", response.status_code)
            response.raise_for_status()
            data = response.json()
            _LOGGER.debug("Auth response: %s", json.dumps(data, indent=2)[:500])
            
            if "data" in data and "obtainKrakenToken" in data["data"]:
                token_data = data["data"]["obtainKrakenToken"]
                self.token = token_data["token"]
                self.refresh_token = token_data["refreshToken"]
                # Set expiry to 5 minutes before actual expiry for safety
                self.token_expires_at = time.time() + 600  # 10 minutes
                _LOGGER.info("Successfully authenticated. Token starts with: %s...", self.token[:30])
                return True
            else:
                _LOGGER.error("Failed to authenticate. Response: %s", data)
                return False
        except Exception as e:
            _LOGGER.error("Authentication error: %s", e, exc_info=True)
            return False
    
    def _ensure_valid_token(self):
        """Ensure we have a valid token, refreshing if necessary."""
        if time.time() >= self.token_expires_at:
            _LOGGER.info("Token expired, re-authenticating")
            self.authenticate()
    
    def fetch_account_numbers(self) -> list[str]:
        """Fetch list of account numbers for the authenticated user."""
        try:
            _LOGGER.info("Fetching account numbers")

            self._ensure_valid_token()
            if not self.token:
                _LOGGER.error("No token available when fetching account numbers")
                return []
            
            headers = {
                "Authorization": self.token
            }
            
            response = self.session.post(
                API_URL,
                headers=headers,
                json={
                    "query": ACCOUNT_LIST_QUERY,
                    "operationName": "AccountNumberList"
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                _LOGGER.error("GraphQL errors fetching account numbers: %s", data["errors"])
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
    
    def _fetch_meter_identifiers(self) -> bool:
        """Fetch meter identifiers (device ID and market supply point ID)."""
        if self.meter_identifiers_fetched:
            return True
            
        if self.market_supply_point_id and self.device_id:
            _LOGGER.debug("Meter identifiers already provided")
            self.meter_identifiers_fetched = True
            return True
        
        try:
            _LOGGER.info("Fetching meter identifiers automatically")
            
            headers = {
                "Authorization": self.token
            }
            
            response = self.session.post(
                API_URL,
                headers=headers,
                json={
                    "query": METER_IDENTIFIERS_QUERY,
                    "variables": {
                        "accountNumber": self.account_number
                    },
                    "operationName": "GetMeterIdentifiers"
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                _LOGGER.error("GraphQL errors fetching meter identifiers: %s", data["errors"])
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
            
            _LOGGER.info("Successfully discovered meter identifiers: MSPID=%s, DeviceID=%s", 
                        self.market_supply_point_id, self.device_id)
            self.meter_identifiers_fetched = True
            return True
            
        except Exception as e:
            _LOGGER.error("Error fetching meter identifiers: %s", e, exc_info=True)
            return False
    
    def get_meter_readings(self, official_reading_date: str | None = None) -> dict[str, Any]:
        """Get meter readings from the API.

        Args:
            official_reading_date: Optional date of last official meter reading.
                                   If provided and mid-month, fetches daily data from that date.
        """
        # Re-authenticate to ensure fresh token
        if not self.authenticate():
            _LOGGER.error("Failed to authenticate before fetching readings")
            return {}

        # Fetch meter identifiers if not already done
        if not self._fetch_meter_identifiers():
            _LOGGER.error("Failed to fetch meter identifiers")
            return {}

        if not self.token:
            _LOGGER.error("No token available after authentication!")
            return {}

        _LOGGER.debug("Using token: %s... (length: %d)", self.token[:30], len(self.token))

        if not self.market_supply_point_id or not self.device_id:
            _LOGGER.error("Missing marketSupplyPointId or deviceId")
            return {}
        
        try:
            # Get data for current week and previous complete week
            # Need to fetch enough to cover: yesterday, 7-day average, current week, AND previous week
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # Calculate how many days back to the start of previous week (Monday)
            today = datetime.now().date()
            days_since_monday = today.weekday()  # 0 = Monday, 6 = Sunday
            current_week_monday = today - timedelta(days=days_since_monday)
            previous_week_monday = current_week_monday - timedelta(days=7)

            # Fetch from previous Monday (14 days back minimum) to ensure we have all data
            start_date = datetime.combine(previous_week_monday, datetime.min.time())

            _LOGGER.info("Fetching daily readings from %s to %s (covers current + previous week)", start_date, end_date)
            
            headers = {
                "Authorization": self.token
            }
            
            # Fetch daily readings using DAY_INTERVAL (matches website behavior)
            daily_response = self.session.post(
                API_URL,
                headers=headers,
                json={
                    "query": SMART_METER_READINGS_QUERY,
                    "variables": {
                        "accountNumber": self.account_number,
                        "startAt": start_date.isoformat() + "Z",
                        "endAt": end_date.isoformat() + "Z",
                        "utilityFilters": [{
                            "waterFilters": {
                                "readingFrequencyType": "DAY_INTERVAL",
                                "marketSupplyPointId": self.market_supply_point_id,
                                "deviceId": self.device_id
                            }
                        }]
                    },
                    "operationName": "SmartMeterReadings"
                }
            )
            
            daily_response.raise_for_status()
            daily_data = daily_response.json()
            
            if "errors" in daily_data:
                _LOGGER.error("GraphQL errors fetching daily data: %s", daily_data["errors"])
                return {}
            
            # Fetch monthly readings (last 12 months for estimation calculations)
            monthly_start = end_date - timedelta(days=365)
            _LOGGER.info("Fetching monthly readings from %s to %s", monthly_start, end_date)
            
            monthly_response = self.session.post(
                API_URL,
                headers=headers,
                json={
                    "query": SMART_METER_READINGS_QUERY,
                    "variables": {
                        "accountNumber": self.account_number,
                        "startAt": monthly_start.isoformat() + "Z",
                        "endAt": end_date.isoformat() + "Z",
                        "utilityFilters": [{
                            "waterFilters": {
                                "readingFrequencyType": "MONTH_INTERVAL",
                                "marketSupplyPointId": self.market_supply_point_id,
                                "deviceId": self.device_id
                            }
                        }]
                    },
                    "operationName": "SmartMeterReadings"
                }
            )
            
            monthly_response.raise_for_status()
            monthly_data = monthly_response.json()
            
            if "errors" in monthly_data:
                _LOGGER.error("GraphQL errors fetching monthly data: %s", monthly_data["errors"])
                # Continue with just daily data
                monthly_measurements = []
            else:
                monthly_properties = monthly_data.get("data", {}).get("account", {}).get("properties", [])
                if monthly_properties:
                    monthly_measurements = monthly_properties[0].get("measurements", {}).get("edges", [])
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
            _LOGGER.info("Found %d daily measurements", len(measurements))

            if not measurements:
                _LOGGER.warning("No measurements found")
                return {}

            # Process daily measurements (already aggregated by API)
            daily_totals = {}
            for measurement in measurements:
                node = measurement["node"]
                try:
                    value = float(node["value"])
                except (ValueError, TypeError) as e:
                    _LOGGER.warning("Invalid measurement value, using 0.0: %s", e)
                    value = 0.0

                start_at = node.get("startAt")

                if start_at:
                    date_str = start_at.split("T")[0]
                    daily_totals[date_str] = value

            _LOGGER.debug("Daily totals: %s", daily_totals)

            # Sort days by date (most recent first)
            sorted_days = sorted(daily_totals.items(), key=lambda x: x[0], reverse=True)

            if not sorted_days:
                _LOGGER.warning("No daily totals calculated")
                return {}

            # Calculate yesterday's date (today - 1 day) to match website behavior
            yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()

            # Get yesterday's total from the specific date
            yesterday_total = daily_totals.get(yesterday, 0.0)
            yesterday_date = yesterday

            _LOGGER.info("Yesterday (%s): %s m³", yesterday_date, yesterday_total)
            
            # Calculate running total and build readings list
            all_readings = []
            total_usage = 0
            
            for date_str, daily_total in sorted_days:
                all_readings.append({
                    "value": round(daily_total, 3),
                    "date": date_str,
                    "unit": "m³"
                })
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
                except (ValueError, TypeError) as e:
                    _LOGGER.warning("Invalid monthly measurement value, using 0.0: %s", e)
                    value = 0.0

                start_at = node.get("startAt")

                if start_at:
                    # Extract year-month
                    date_str = start_at.split("T")[0]
                    monthly_readings.append({
                        "value": round(value, 3),
                        "start_date": date_str,
                        "unit": "m³"
                    })

            _LOGGER.info("Found %d monthly readings", len(monthly_readings))

            # Fetch daily readings since official meter reading if mid-month
            daily_readings_since_official = []
            if official_reading_date:
                try:
                    official_date_str = official_reading_date.split("T")[0] if "T" in official_reading_date else official_reading_date
                    official_dt = datetime.fromisoformat(official_date_str)
                    official_month_start = official_dt.replace(day=1)

                    # Check if official reading is mid-month (not on the 1st)
                    if official_dt.day > 1:
                        _LOGGER.info("Official reading is mid-month (%s), fetching daily data from that date", official_date_str)

                        # Fetch daily data from official reading date to end of that month
                        # We need to determine the end of the month
                        if official_dt.month == 12:
                            next_month = official_dt.replace(year=official_dt.year + 1, month=1, day=1)
                        else:
                            next_month = official_dt.replace(month=official_dt.month + 1, day=1)

                        partial_month_end = next_month  # First day of next month

                        _LOGGER.info("Fetching partial month daily readings from %s to %s", official_date_str, partial_month_end.isoformat())

                        partial_response = self.session.post(
                            API_URL,
                            headers=headers,
                            json={
                                "query": SMART_METER_READINGS_QUERY,
                                "variables": {
                                    "accountNumber": self.account_number,
                                    "startAt": official_dt.isoformat() + "Z",
                                    "endAt": partial_month_end.isoformat() + "Z",
                                    "utilityFilters": [{
                                        "waterFilters": {
                                            "readingFrequencyType": "DAY_INTERVAL",
                                            "marketSupplyPointId": self.market_supply_point_id,
                                            "deviceId": self.device_id
                                        }
                                    }]
                                },
                                "operationName": "SmartMeterReadings"
                            }
                        )

                        partial_response.raise_for_status()
                        partial_data = partial_response.json()

                        if "errors" not in partial_data:
                            partial_properties = partial_data.get("data", {}).get("account", {}).get("properties", [])
                            if partial_properties:
                                partial_measurements = partial_properties[0].get("measurements", {}).get("edges", [])
                                for measurement in partial_measurements:
                                    node = measurement["node"]
                                    try:
                                        value = float(node["value"])
                                    except (ValueError, TypeError) as e:
                                        _LOGGER.warning("Invalid partial month measurement value, using 0.0: %s", e)
                                        value = 0.0

                                    start_at = node.get("startAt")
                                    if start_at:
                                        date_str = start_at.split("T")[0]
                                        daily_readings_since_official.append({
                                            "value": round(value, 3),
                                            "date": date_str,
                                            "unit": "m³"
                                        })

                                _LOGGER.info("Found %d daily readings for partial month", len(daily_readings_since_official))
                        else:
                            _LOGGER.warning("Errors fetching partial month data: %s", partial_data["errors"])

                except (ValueError, AttributeError) as e:
                    _LOGGER.error("Error processing official reading date: %s - %s", official_reading_date, e)

            # Calculate week-to-date and previous week usage
            week_to_date_usage = 0
            previous_week_usage = 0
            week_start_date = None
            previous_week_start_date = None
            previous_week_end_date = None
            days_in_current_week = 0

            today = datetime.now().date()
            # Get Monday of current week (weekday() returns 0 for Monday)
            days_since_monday = today.weekday()
            current_week_monday = today - timedelta(days=days_since_monday)
            previous_week_monday = current_week_monday - timedelta(days=7)
            previous_week_sunday = current_week_monday - timedelta(days=1)

            week_start_date = current_week_monday.isoformat()
            previous_week_start_date = previous_week_monday.isoformat()
            previous_week_end_date = previous_week_sunday.isoformat()

            _LOGGER.debug("Current week starts: %s", week_start_date)
            _LOGGER.debug("Previous week: %s to %s", previous_week_start_date, previous_week_end_date)

            for date_str, daily_total in daily_totals.items():
                try:
                    reading_date = datetime.fromisoformat(date_str).date()

                    # Current week (Monday to today)
                    if current_week_monday <= reading_date <= today:
                        week_to_date_usage += daily_total
                        days_in_current_week += 1
                        _LOGGER.debug("  %s: %s m³ (current week)", date_str, daily_total)

                    # Previous week (Monday to Sunday)
                    elif previous_week_monday <= reading_date <= previous_week_sunday:
                        previous_week_usage += daily_total
                        _LOGGER.debug("  %s: %s m³ (previous week)", date_str, daily_total)
                except (ValueError, AttributeError) as e:
                    _LOGGER.warning("Invalid date format for week calculation: %s - %s", date_str, e)
                    continue

            _LOGGER.info("Week to date usage: %s m³ (%d days)", week_to_date_usage, days_in_current_week)
            _LOGGER.info("Previous week usage: %s m³", previous_week_usage)
            
            return {
                "meter_id": f"{self.market_supply_point_id}_{self.device_id}",
                "yesterday_usage": round(yesterday_total, 3),
                "yesterday_date": yesterday_date,
                "daily_average": round(avg_daily_usage, 3),
                "total_7day_usage": round(total_usage, 3),
                "week_to_date_usage": round(week_to_date_usage, 3),
                "previous_week_usage": round(previous_week_usage, 3),
                "week_start_date": week_start_date,
                "previous_week_start_date": previous_week_start_date,
                "previous_week_end_date": previous_week_end_date,
                "days_in_current_week": days_in_current_week,
                "unit": "m³",
                "all_readings": all_readings,
                "monthly_readings": monthly_readings,
                "daily_readings_since_official": daily_readings_since_official
            }
            
        except requests.exceptions.HTTPError as e:
            _LOGGER.error("HTTP error fetching meter readings: %s - Response: %s", 
                         e, e.response.text if hasattr(e, 'response') else 'No response')
            return {}
        except Exception as e:
            _LOGGER.error("Error fetching meter readings: %s", e, exc_info=True)
            return {}
    
    def get_manual_meter_readings(self) -> dict[str, Any]:
        """Get manual meter readings from the API."""
        self._ensure_valid_token()
        
        try:
            # Get readings from the past year
            active_from = (datetime.now() - timedelta(days=365)).isoformat() + "Z"
            
            _LOGGER.debug("Fetching manual meter readings")
            
            headers = {
                "Authorization": self.token
            }
            
            response = self.session.post(
                API_URL,
                headers=headers,
                json={
                    "query": METER_READINGS_QUERY,
                    "variables": {
                        "accountNumber": self.account_number,
                        "activeFrom": active_from
                    },
                    "operationName": "MeterReadings"
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                _LOGGER.error("GraphQL errors fetching manual readings: %s", data["errors"])
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
                "usage_since_last": round(usage_since_last, 3) if usage_since_last else None,
                "days_since_last": days_since_last,
                "avg_daily_usage": round(avg_daily_usage, 3) if avg_daily_usage else None,
                "all_readings": [
                    {
                        "value": float(r["node"]["valueCubicMetres"]),
                        "date": r["node"]["readingDate"],
                        "source": r["node"]["source"]
                    }
                    for r in readings
                ]
            }
            
        except Exception as e:
            _LOGGER.error("Error fetching manual meter readings: %s", e, exc_info=True)
            return {}

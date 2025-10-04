"""API client for Severn Trent Water."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import requests

from .const import API_URL, AUTH_MUTATION, ACCOUNT_LIST_QUERY, METER_IDENTIFIERS_QUERY, METER_READINGS_QUERY, SMART_METER_READINGS_QUERY

_LOGGER = logging.getLogger(__name__)

class SevernTrentAPI:
    """API client for Severn Trent Water."""
    
    def __init__(self, email: str, password: str, account_number: str = None, market_supply_point_id: str = None, device_id: str = None):
        """Initialize the API client."""
        self.email = email
        self.password = password
        self.account_number = account_number
        self.market_supply_point_id = market_supply_point_id
        self.device_id = device_id
        self.token = None
        self.refresh_token = None
        self.token_expires_at = 0
        self.session = requests.Session()
        self.meter_identifiers_fetched = False
    
    def authenticate(self) -> bool:
        """Authenticate with the API and obtain JWT token."""
        try:
            _LOGGER.info("Attempting authentication for %s", self.email)
            _LOGGER.debug("Account number: %s", self.account_number)
            
            response = self.session.post(
                API_URL,
                json={
                    "query": AUTH_MUTATION,
                    "variables": {
                        "input": {
                            "email": self.email,
                            "password": self.password
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
    
    def get_meter_readings(self) -> dict[str, Any]:
        """Get meter readings from the API."""
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
            # Get yesterday's data (since today's data isn't available yet)
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=7)  # Get last 7 days
            
            _LOGGER.info("Fetching readings from %s to %s", start_date, end_date)
            _LOGGER.debug("Using account: %s, MSPI: %s, Device: %s", 
                         self.account_number, self.market_supply_point_id, self.device_id)
            
            headers = {
                "Authorization": self.token
            }
            
            _LOGGER.info("Making request with headers: %s", {k: v[:30] + "..." if len(v) > 30 else v for k, v in headers.items()})
            _LOGGER.debug("Full token: %s", self.token)
            
            request_payload = {
                "query": SMART_METER_READINGS_QUERY,
                "variables": {
                    "accountNumber": self.account_number,
                    "startAt": start_date.isoformat() + "Z",
                    "endAt": end_date.isoformat() + "Z",
                    "utilityFilters": [{
                        "waterFilters": {
                            "readingFrequencyType": "HOUR_INTERVAL",
                            "marketSupplyPointId": self.market_supply_point_id,
                            "deviceId": self.device_id
                        }
                    }]
                },
                "operationName": "SmartMeterReadings"
            }
            
            _LOGGER.debug("Request payload: %s", request_payload)
            
            response = self.session.post(
                API_URL,
                headers=headers,
                json=request_payload
            )
            
            _LOGGER.debug("Smart meter readings response status: %s", response.status_code)
            response.raise_for_status()
            data = response.json()
            
            # Log the full response for debugging
            _LOGGER.debug("Smart meter readings full response: %s", json.dumps(data, indent=2))
            
            if "errors" in data:
                _LOGGER.error("GraphQL errors: %s", data["errors"])
                return {}
            
            if "data" not in data or "account" not in data["data"]:
                _LOGGER.error("Unexpected API response structure. Full response: %s", json.dumps(data, indent=2))
                return {}
            
            if data["data"]["account"] is None:
                _LOGGER.error("Account is None in response. Full response: %s", json.dumps(data, indent=2))
                return {}
            
            properties = data["data"]["account"].get("properties", [])
            if not properties:
                _LOGGER.warning("No properties in response. Full response: %s", json.dumps(data, indent=2))
                return {}
            
            measurements = properties[0].get("measurements", {}).get("edges", [])
            _LOGGER.info("Found %d measurements", len(measurements))
            
            if not measurements:
                _LOGGER.warning("No measurements found")
                return {}
            
            # Group hourly measurements by day
            daily_totals = {}
            for measurement in measurements:
                node = measurement["node"]
                # Handle scientific notation (e.g., "0E-18" means 0)
                try:
                    value = float(node["value"])
                except (ValueError, TypeError):
                    value = 0.0
                    
                start_at = node.get("startAt")
                
                if start_at:
                    # Extract just the date part (YYYY-MM-DD)
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
                all_readings.append({
                    "value": round(daily_total, 3),
                    "date": date_str,
                    "unit": "m³"
                })
                total_usage += daily_total
            
            # Calculate average daily usage
            num_days = len(all_readings)
            avg_daily_usage = total_usage / num_days if num_days > 0 else 0
            
            return {
                "meter_id": f"{self.market_supply_point_id}_{self.device_id}",
                "yesterday_usage": round(yesterday_total, 3),
                "yesterday_date": yesterday_date,
                "daily_average": round(avg_daily_usage, 3),
                "total_7day_usage": round(total_usage, 3),
                "unit": "m³",
                "all_readings": all_readings
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

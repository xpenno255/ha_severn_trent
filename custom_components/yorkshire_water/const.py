"""Constants for the Yorkshire Water integration."""

from __future__ import annotations

DOMAIN = "yorkshire_water"

CONF_ACCOUNT_ID = "account_id"
CONF_ACCOUNT_REFERENCE = "account_reference"
CONF_AUTH_TYPE = "auth_type"
CONF_BEARER_TOKEN = "bearer_token"
CONF_METER_ID = "meter_id"
CONF_METER_REFERENCE = "meter_reference"
CONF_SESSION_TOKEN = "session_token"

AUTH_TYPE_BEARER_TOKEN = "bearer_token"
AUTH_TYPE_SESSION_TOKEN = "session_token"

DEFAULT_NAME = "Yorkshire Water"
DEFAULT_SCAN_INTERVAL_HOURS = 6

# Discovered Yorkshire Water portal routes. Response schemas are still unknown,
# so production data fetch methods remain disabled below until redacted response
# JSON structures are supplied.
YORKSHIRE_WATER_TOKEN_ENDPOINT = "https://login.yorkshirewater.com/connect/token"
YORKSHIRE_WATER_SMART_METER_API_BASE_URL = (
    "https://my.yorkshirewater.com/api/account/smartmeter"
)
YORKSHIRE_WATER_METER_DETAILS_ENDPOINT_PATH = "/meter-details"
YORKSHIRE_WATER_CURRENT_CONSUMPTION_ENDPOINT_PATH = "/current-consumption"
YORKSHIRE_WATER_YOUR_USAGE_ENDPOINT_PATH = "/your-usage"

YORKSHIRE_WATER_API_BASE_URL: str | None = YORKSHIRE_WATER_SMART_METER_API_BASE_URL
YORKSHIRE_WATER_CURRENT_CONSUMPTION_PATH: str | None = None
YORKSHIRE_WATER_DAILY_CONSUMPTION_PATH: str | None = None
YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH: str | None = None

"""Constants for the Yorkshire Water integration."""

from __future__ import annotations

DOMAIN = "yorkshire_water"

CONF_ACCOUNT_ID = "account_id"
CONF_AUTH_TYPE = "auth_type"
CONF_METER_ID = "meter_id"
CONF_SESSION_TOKEN = "session_token"

AUTH_TYPE_SESSION_TOKEN = "session_token"

DEFAULT_NAME = "Yorkshire Water"
DEFAULT_SCAN_INTERVAL_HOURS = 6

# Yorkshire Water portal endpoint details still need to be captured from a live
# account session. Keep these disabled until the request/response contract is
# known, rather than leaving the upstream Kraken GraphQL API active.
YORKSHIRE_WATER_API_BASE_URL: str | None = None
YORKSHIRE_WATER_CURRENT_CONSUMPTION_PATH: str | None = None
YORKSHIRE_WATER_DAILY_CONSUMPTION_PATH: str | None = None
YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH: str | None = None

"""Constants for the Yorkshire Water integration."""

from __future__ import annotations

DOMAIN = "yorkshire_water"

CONF_ACCOUNT_ID = "account_id"
CONF_ACCOUNT_REFERENCE = "account_reference"
CONF_AUTH_TYPE = "auth_type"
CONF_BEARER_TOKEN = "bearer_token"
CONF_METER_ID = "meter_id"
CONF_METER_REFERENCE = "meter_reference"
CONF_OAUTH_AUTHORIZATION_CODE = "oauth_authorization_code"
CONF_OAUTH_CALLBACK_URL = "oauth_callback_url"
CONF_OAUTH_CODE_VERIFIER = "oauth_code_verifier"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SESSION_TOKEN = "session_token"
CONF_TOKEN_EXPIRES_AT = "token_expires_at"
CONF_TOKEN_RESPONSE_JSON = "token_response_json"

AUTH_TYPE_BEARER_TOKEN = "bearer_token"
AUTH_TYPE_OAUTH_PKCE = "oauth_pkce"
AUTH_TYPE_SESSION_TOKEN = "session_token"

DEFAULT_NAME = "Yorkshire Water"
DEFAULT_SCAN_INTERVAL_HOURS = 6

# Discovered Yorkshire Water portal routes. Response schemas are still unknown,
# so production data fetch methods remain disabled below until redacted response
# JSON structures are supplied.
YORKSHIRE_WATER_TOKEN_ENDPOINT = "https://login.yorkshirewater.com/connect/token"
YORKSHIRE_WATER_OAUTH_CLIENT_ID = "css-onlineaccount-fe"
YORKSHIRE_WATER_OAUTH_REDIRECT_URI = (
    "https://my.yorkshirewater.com/account/callback/response"
)
YORKSHIRE_WATER_OAUTH_SCOPES = (
    "openid",
    "user-names",
    "css-onlineaccount-api",
    "css-registration-api",
)
YORKSHIRE_WATER_SMART_METER_API_BASE_URL = (
    "https://my.yorkshirewater.com/api/account/smartmeter"
)
YORKSHIRE_WATER_METER_DETAILS_ENDPOINT_PATH = "/meter-details"
YORKSHIRE_WATER_CURRENT_CONSUMPTION_ENDPOINT_PATH = "/current-consumption"
YORKSHIRE_WATER_DAILY_CONSUMPTION_ENDPOINT_PATH = "/daily-consumption"
YORKSHIRE_WATER_YOUR_USAGE_ENDPOINT_PATH = "/your-usage"

YORKSHIRE_WATER_API_BASE_URL: str | None = YORKSHIRE_WATER_SMART_METER_API_BASE_URL
YORKSHIRE_WATER_CURRENT_CONSUMPTION_PATH: str | None = None
YORKSHIRE_WATER_DAILY_CONSUMPTION_PATH: str | None = None
YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH: str | None = None

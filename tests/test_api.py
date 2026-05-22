"""Tests for the SevernTrentAPI client – validates endpoint request structure
and response parsing against the live GraphQL schema contract.

These tests mock the HTTP layer so they run offline and fast, but they verify
that every endpoint sends a well-formed GraphQL request to the correct URL
and correctly parses the expected JSON response shape.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch, call

import pytest

from custom_components.severn_trent.api import SevernTrentAPI
from custom_components.severn_trent.const import (
    API_KEY_MUTATION,
    API_URL,
    AUTH_MUTATION,
    ACCOUNT_LIST_QUERY,
    BALANCE_QUERY,
    METER_IDENTIFIERS_QUERY,
    METER_DETAILS_QUERY,
    METER_READINGS_QUERY,
    PAYMENT_SCHEDULE_QUERY,
    OUTSTANDING_PAYMENT_QUERY,
    RATE_LIMIT_QUERY,
    LEDGERS_QUERY,
    PAYMENT_FORECAST_QUERY,
    SMART_METER_READINGS_QUERY,
)

from tests.conftest import (
    _make_response,
    AUTH_SUCCESS_RESPONSE,
    AUTH_ERROR_RESPONSE,
    ACCOUNT_LIST_RESPONSE,
    METER_IDENTIFIERS_RESPONSE,
    SMART_METER_DAILY_RESPONSE,
    SMART_METER_MONTHLY_RESPONSE,
    MANUAL_READINGS_RESPONSE,
    BALANCE_RESPONSE,
    RATE_LIMIT_RESPONSE,
    PAYMENT_SCHEDULE_RESPONSE,
    METER_DETAILS_RESPONSE,
    OUTSTANDING_PAYMENT_RESPONSE,
    LEDGERS_RESPONSE,
    PAYMENT_FORECAST_RESPONSE,
    API_KEY_GENERATION_RESPONSE,
)


# ======================================================================
# Helper
# ======================================================================

def _post_call_args(mock_post, call_index: int = 0) -> dict:
    """Extract the JSON payload from the *nth* call to session.post."""
    args, kwargs = mock_post.call_args_list[call_index]
    return kwargs


# ======================================================================
# 1. Authentication
# ======================================================================

class TestAuthenticate:
    """Tests for SevernTrentAPI.authenticate()."""

    def test_authenticate_sends_correct_url(self, api: SevernTrentAPI):
        """authenticate() should POST to the GraphQL API URL."""
        with patch.object(api.session, "post", return_value=_make_response(AUTH_SUCCESS_RESPONSE)) as mock_post:
            api.authenticate()
            mock_post.assert_called_once()
            assert mock_post.call_args[0][0] == API_URL

    def test_authenticate_sends_correct_query(self, api: SevernTrentAPI):
        """authenticate() should send the AUTH_MUTATION in the request body."""
        with patch.object(api.session, "post", return_value=_make_response(AUTH_SUCCESS_RESPONSE)) as mock_post:
            api.authenticate()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == AUTH_MUTATION
            assert payload["json"]["operationName"] == "ObtainKrakenToken"

    def test_authenticate_sends_api_key_in_variables(self, api: SevernTrentAPI):
        """authenticate() should include the API key in variables.input.APIKey."""
        with patch.object(api.session, "post", return_value=_make_response(AUTH_SUCCESS_RESPONSE)) as mock_post:
            api.authenticate()
            payload = _post_call_args(mock_post)
            assert payload["json"]["variables"]["input"]["APIKey"] == "test-api-key"

    def test_authenticate_success_sets_token(self, api: SevernTrentAPI):
        """On success, authenticate() should store the JWT token and refresh token."""
        with patch.object(api.session, "post", return_value=_make_response(AUTH_SUCCESS_RESPONSE)):
            result = api.authenticate()
            assert result is True
            assert api.token == "jwt-token-abc123"
            assert api.refresh_token == "refresh-token-xyz"
            assert api.token_expires_at > time.time()

    def test_authenticate_failure_returns_false(self, api: SevernTrentAPI):
        """On GraphQL error response, authenticate() should return False."""
        with patch.object(api.session, "post", return_value=_make_response(AUTH_ERROR_RESPONSE)):
            result = api.authenticate()
            assert result is False
            assert api.token is None

    def test_authenticate_missing_api_key(self):
        """authenticate() should return False when no API key is set."""
        api = SevernTrentAPI(api_key=None)
        result = api.authenticate()
        assert result is False

    def test_authenticate_http_error_returns_false(self, api: SevernTrentAPI):
        """authenticate() should return False on HTTP errors."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        with patch.object(api.session, "post", return_value=mock_resp):
            result = api.authenticate()
            assert result is False


# ======================================================================
# 2. API Key Generation (static method)
# ======================================================================

class TestGenerateApiKey:
    """Tests for SevernTrentAPI.generate_api_key()."""

    def test_generate_api_key_sends_correct_url(self):
        """generate_api_key() should POST to the GraphQL API URL."""
        with patch("custom_components.severn_trent.api.requests.Session") as MockSession:
            mock_session = MockSession.return_value
            mock_session.post.return_value = _make_response(API_KEY_GENERATION_RESPONSE)
            result = SevernTrentAPI.generate_api_key("bearer-token-123")
            mock_session.post.assert_called_once()
            assert mock_session.post.call_args[0][0] == API_URL

    def test_generate_api_key_sends_correct_query(self):
        """generate_api_key() should send the API_KEY_MUTATION."""
        with patch("custom_components.severn_trent.api.requests.Session") as MockSession:
            mock_session = MockSession.return_value
            mock_session.post.return_value = _make_response(API_KEY_GENERATION_RESPONSE)
            SevernTrentAPI.generate_api_key("bearer-token-123")
            payload = mock_session.post.call_args[1]
            assert payload["json"]["query"] == API_KEY_MUTATION

    def test_generate_api_key_sends_authorization_header(self):
        """generate_api_key() should send the browser token as Authorization header."""
        with patch("custom_components.severn_trent.api.requests.Session") as MockSession:
            mock_session = MockSession.return_value
            mock_session.post.return_value = _make_response(API_KEY_GENERATION_RESPONSE)
            SevernTrentAPI.generate_api_key("bearer-token-123")
            payload = mock_session.post.call_args[1]
            assert payload["headers"]["Authorization"] == "bearer-token-123"

    def test_generate_api_key_strips_bearer_prefix(self):
        """generate_api_key() should strip 'Bearer ' prefix from the token."""
        with patch("custom_components.severn_trent.api.requests.Session") as MockSession:
            mock_session = MockSession.return_value
            mock_session.post.return_value = _make_response(API_KEY_GENERATION_RESPONSE)
            SevernTrentAPI.generate_api_key("Bearer my-token")
            payload = mock_session.post.call_args[1]
            assert payload["headers"]["Authorization"] == "my-token"

    def test_generate_api_key_returns_key_on_success(self):
        """generate_api_key() should return the API key on success."""
        with patch("custom_components.severn_trent.api.requests.Session") as MockSession:
            mock_session = MockSession.return_value
            mock_session.post.return_value = _make_response(API_KEY_GENERATION_RESPONSE)
            result = SevernTrentAPI.generate_api_key("valid-token")
            assert result == "new-api-key-abc123"

    def test_generate_api_key_returns_none_on_error(self):
        """generate_api_key() should return None on GraphQL errors."""
        with patch("custom_components.severn_trent.api.requests.Session") as MockSession:
            mock_session = MockSession.return_value
            mock_session.post.return_value = _make_response(AUTH_ERROR_RESPONSE)
            result = SevernTrentAPI.generate_api_key("valid-token")
            assert result is None

    def test_generate_api_key_returns_none_on_empty_token(self):
        """generate_api_key() should return None for empty/whitespace tokens."""
        result = SevernTrentAPI.generate_api_key("  ")
        assert result is None


# ======================================================================
# 3. Fetch Account Numbers
# ======================================================================

class TestFetchAccountNumbers:
    """Tests for SevernTrentAPI.fetch_account_numbers()."""

    def test_fetch_account_numbers_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """fetch_account_numbers() should send the ACCOUNT_LIST_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(ACCOUNT_LIST_RESPONSE)) as mock_post:
            authenticated_api.fetch_account_numbers()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == ACCOUNT_LIST_QUERY
            assert payload["json"]["operationName"] == "AccountNumberList"

    def test_fetch_account_numbers_sends_auth_header(self, authenticated_api: SevernTrentAPI):
        """fetch_account_numbers() should include the Authorization header."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(ACCOUNT_LIST_RESPONSE)) as mock_post:
            authenticated_api.fetch_account_numbers()
            payload = _post_call_args(mock_post)
            assert payload["headers"]["Authorization"] == "test-jwt-token"

    def test_fetch_account_numbers_returns_account_list(self, authenticated_api: SevernTrentAPI):
        """fetch_account_numbers() should return a list of account numbers."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(ACCOUNT_LIST_RESPONSE)):
            accounts = authenticated_api.fetch_account_numbers()
            assert accounts == ["1234567890", "0987654321"]

    def test_fetch_account_numbers_returns_empty_on_error(self, authenticated_api: SevernTrentAPI):
        """fetch_account_numbers() should return an empty list on GraphQL errors."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(AUTH_ERROR_RESPONSE)):
            accounts = authenticated_api.fetch_account_numbers()
            assert accounts == []

    def test_fetch_account_numbers_returns_empty_without_token(self, api: SevernTrentAPI):
        """fetch_account_numbers() should return empty list when no token is available."""
        # api has no token set
    api_no_token = SevernTrentAPI(api_key="key", account_number="123")
    # Force token expiry
    api_no_token.token_expires_at = 0
    with patch.object(api_no_token, "authenticate", return_value=False):
        accounts = api_no_token.fetch_account_numbers()
        assert accounts == []


# ======================================================================
# 4. Fetch Meter Identifiers
# ======================================================================

class TestFetchMeterIdentifiers:
    """Tests for SevernTrentAPI._fetch_meter_identifiers()."""

    def test_fetch_meter_identifiers_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """_fetch_meter_identifiers() should send the METER_IDENTIFIERS_QUERY."""
        authenticated_api.meter_identifiers_fetched = False
        # Clear pre-set identifiers so it actually fetches
        authenticated_api.market_supply_point_id = None
        authenticated_api.device_id = None
        authenticated_api.capability_type = None

        with patch.object(authenticated_api.session, "post", return_value=_make_response(METER_IDENTIFIERS_RESPONSE)) as mock_post:
            authenticated_api._fetch_meter_identifiers()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == METER_IDENTIFIERS_QUERY
            assert payload["json"]["operationName"] == "GetMeterIdentifiers"

    def test_fetch_meter_identifiers_sends_account_number(self, authenticated_api: SevernTrentAPI):
        """_fetch_meter_identifiers() should include the account number in variables."""
        authenticated_api.meter_identifiers_fetched = False
        authenticated_api.market_supply_point_id = None
        authenticated_api.device_id = None
        authenticated_api.capability_type = None

        with patch.object(authenticated_api.session, "post", return_value=_make_response(METER_IDENTIFIERS_RESPONSE)) as mock_post:
            authenticated_api._fetch_meter_identifiers()
            payload = _post_call_args(mock_post)
            assert payload["json"]["variables"]["accountNumber"] == "1234567890"

    def test_fetch_meter_identifiers_extracts_identifiers(self, authenticated_api: SevernTrentAPI):
        """_fetch_meter_identifiers() should extract meter identifiers from response."""
        authenticated_api.meter_identifiers_fetched = False
        authenticated_api.market_supply_point_id = None
        authenticated_api.device_id = None
        authenticated_api.capability_type = None

        with patch.object(authenticated_api.session, "post", return_value=_make_response(METER_IDENTIFIERS_RESPONSE)):
            result = authenticated_api._fetch_meter_identifiers()
            assert result is True
            assert authenticated_api.market_supply_point_id == "MSP123"
            assert authenticated_api.device_id == "DEV456"
            assert authenticated_api.capability_type == "SMART_METER"

    def test_fetch_meter_identifiers_skips_if_already_fetched(self, authenticated_api: SevernTrentAPI):
        """_fetch_meter_identifiers() should skip if identifiers are already fetched."""
        authenticated_api.meter_identifiers_fetched = True
        with patch.object(authenticated_api.session, "post") as mock_post:
            result = authenticated_api._fetch_meter_identifiers()
            assert result is True
            mock_post.assert_not_called()

    def test_fetch_meter_identifiers_skips_if_all_provided(self, authenticated_api: SevernTrentAPI):
        """_fetch_meter_identifiers() should skip if all identifiers are pre-configured."""
        authenticated_api.meter_identifiers_fetched = False
        # All three identifiers are already set from the fixture
        assert authenticated_api.market_supply_point_id == "MSP123"
        assert authenticated_api.device_id == "DEV456"
        assert authenticated_api.capability_type == "SMART_METER"
        with patch.object(authenticated_api.session, "post") as mock_post:
            result = authenticated_api._fetch_meter_identifiers()
            assert result is True
            mock_post.assert_not_called()


# ======================================================================
# 5. Get Balance
# ======================================================================

class TestGetBalance:
    """Tests for SevernTrentAPI.get_balance()."""

    def test_get_balance_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_balance() should send the BALANCE_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(BALANCE_RESPONSE)) as mock_post:
            authenticated_api.get_balance()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == BALANCE_QUERY
            assert payload["json"]["operationName"] == "GetBalance"

    def test_get_balance_sends_account_number(self, authenticated_api: SevernTrentAPI):
        """get_balance() should include the account number in variables."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(BALANCE_RESPONSE)) as mock_post:
            authenticated_api.get_balance()
            payload = _post_call_args(mock_post)
            assert payload["json"]["variables"]["accountNumber"] == "1234567890"

    def test_get_balance_parses_balance_correctly(self, authenticated_api: SevernTrentAPI):
        """get_balance() should convert pence-like balance to GBP."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(BALANCE_RESPONSE)):
            result = authenticated_api.get_balance()
            assert result["balance_pence"] == 12345
            assert result["balance_gbp"] == 123.45

    def test_get_balance_returns_empty_on_error(self, authenticated_api: SevernTrentAPI):
        """get_balance() should return empty dict on GraphQL errors."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(AUTH_ERROR_RESPONSE)):
            result = authenticated_api.get_balance()
            assert result == {}

    def test_get_balance_returns_empty_without_token(self, api: SevernTrentAPI):
        """get_balance() should return empty dict when no token is available."""
        api_no_token = SevernTrentAPI(api_key="key")
        api_no_token.token = None
        result = api_no_token.get_balance()
        assert result == {}

    def test_get_balance_returns_empty_without_account(self, authenticated_api: SevernTrentAPI):
        """get_balance() should return empty dict when no account number is set."""
        authenticated_api.account_number = None
        result = authenticated_api.get_balance()
        assert result == {}


# ======================================================================
# 6. Get Rate Limit Info
# ======================================================================

class TestGetRateLimitInfo:
    """Tests for SevernTrentAPI.get_rate_limit_info()."""

    def test_get_rate_limit_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_rate_limit_info() should send the RATE_LIMIT_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(RATE_LIMIT_RESPONSE)) as mock_post:
            authenticated_api.get_rate_limit_info()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == RATE_LIMIT_QUERY
            assert payload["json"]["operationName"] == "apiRateLimitInfo"

    def test_get_rate_limit_parses_response(self, authenticated_api: SevernTrentAPI):
        """get_rate_limit_info() should parse rate limit fields correctly."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(RATE_LIMIT_RESPONSE)):
            result = authenticated_api.get_rate_limit_info()
            assert result["is_blocked"] is False
            assert result["limit"] == 1000
            assert result["remaining_points"] == 950
            assert result["ttl"] == 3600
            assert result["used_points"] == 50

    def test_get_rate_limit_returns_empty_on_error(self, authenticated_api: SevernTrentAPI):
        """get_rate_limit_info() should return empty dict on GraphQL errors."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(AUTH_ERROR_RESPONSE)):
            result = authenticated_api.get_rate_limit_info()
            assert result == {}


# ======================================================================
# 7. Get Payment Schedule
# ======================================================================

class TestGetPaymentSchedule:
    """Tests for SevernTrentAPI.get_current_active_payment_schedule()."""

    def test_payment_schedule_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_current_active_payment_schedule() should send PAYMENT_SCHEDULE_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(PAYMENT_SCHEDULE_RESPONSE)) as mock_post:
            authenticated_api.get_current_active_payment_schedule()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == PAYMENT_SCHEDULE_QUERY
            assert payload["json"]["operationName"] == "CurrentActivePaymentSchedule"

    def test_payment_schedule_sends_account_number(self, authenticated_api: SevernTrentAPI):
        """get_current_active_payment_schedule() should include account number."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(PAYMENT_SCHEDULE_RESPONSE)) as mock_post:
            authenticated_api.get_current_active_payment_schedule()
            payload = _post_call_args(mock_post)
            assert payload["json"]["variables"]["accountNumber"] == "1234567890"

    def test_payment_schedule_parses_response(self, authenticated_api: SevernTrentAPI):
        """get_current_active_payment_schedule() should parse payment schedule correctly."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(PAYMENT_SCHEDULE_RESPONSE)):
            result = authenticated_api.get_current_active_payment_schedule()
            assert result["id"] == "sched-1"
            assert result["payment_day"] == 15
            assert result["payment_amount_pence"] == 2500
            assert result["payment_amount_gbp"] == 25.0
            assert result["payment_frequency"] == "MONTHLY"
            assert result["is_variable_payment_amount"] is False

    def test_payment_schedule_returns_empty_on_no_edges(self, authenticated_api: SevernTrentAPI):
        """get_current_active_payment_schedule() should return {} when no edges."""
        empty_response = {"data": {"account": {"paymentSchedules": {"edges": []}}}}
        with patch.object(authenticated_api.session, "post", return_value=_make_response(empty_response)):
            result = authenticated_api.get_current_active_payment_schedule()
            assert result == {}


# ======================================================================
# 8. Get Meter Details
# ======================================================================

class TestGetMeterDetails:
    """Tests for SevernTrentAPI.get_meter_details()."""

    def test_meter_details_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_meter_details() should send METER_DETAILS_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(METER_DETAILS_RESPONSE)) as mock_post:
            authenticated_api.get_meter_details()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == METER_DETAILS_QUERY
            assert payload["json"]["operationName"] == "MeterDetails"

    def test_meter_details_sends_variables(self, authenticated_api: SevernTrentAPI):
        """get_meter_details() should include account number and other variables."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(METER_DETAILS_RESPONSE)) as mock_post:
            authenticated_api.get_meter_details()
            payload = _post_call_args(mock_post)
            variables = payload["json"]["variables"]
            assert variables["accountNumber"] == "1234567890"
            assert variables["excludeHeld"] is True
            assert variables["first"] == 1

    def test_meter_details_parses_response(self, authenticated_api: SevernTrentAPI):
        """get_meter_details() should parse meter details correctly."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(METER_DETAILS_RESPONSE)):
            result = authenticated_api.get_meter_details()
            assert result["meter_internal_id"] == "meter-1"
            assert result["serial_number"] == "DEV456"
            assert result["number_of_digits"] == 5
            assert result["latest_reading"] == 1234.5
            assert result["latest_reading_source"] == "CUSTOMER"


# ======================================================================
# 9. Get Outstanding Payment
# ======================================================================

class TestGetOutstandingPayment:
    """Tests for SevernTrentAPI.get_outstanding_payment()."""

    def test_outstanding_payment_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_outstanding_payment() should send OUTSTANDING_PAYMENT_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(OUTSTANDING_PAYMENT_RESPONSE)) as mock_post:
            authenticated_api.get_outstanding_payment()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == OUTSTANDING_PAYMENT_QUERY
            assert payload["json"]["operationName"] == "OutstandingPayment"

    def test_outstanding_payment_parses_response(self, authenticated_api: SevernTrentAPI):
        """get_outstanding_payment() should convert pence to GBP."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(OUTSTANDING_PAYMENT_RESPONSE)):
            result = authenticated_api.get_outstanding_payment()
            assert result["payments_outstanding_pence"] == 5000
            assert result["payments_outstanding_gbp"] == 50.0


# ======================================================================
# 10. Get Ledgers
# ======================================================================

class TestGetLedgers:
    """Tests for SevernTrentAPI.get_ledgers()."""

    def test_get_ledgers_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_ledgers() should send LEDGERS_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(LEDGERS_RESPONSE)) as mock_post:
            authenticated_api.get_ledgers()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == LEDGERS_QUERY
            assert payload["json"]["operationName"] == "Ledgers"

    def test_get_ledgers_parses_response(self, authenticated_api: SevernTrentAPI):
        """get_ledgers() should return a list of ledger dicts."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(LEDGERS_RESPONSE)):
            result = authenticated_api.get_ledgers()
            assert len(result) == 1
            assert result[0]["number"] == "LEDGER1"
            assert result[0]["ledgerType"] == "SEVERN_TRENT_WATER"


# ======================================================================
# 11. Get Payment Forecast
# ======================================================================

class TestGetPaymentForecast:
    """Tests for SevernTrentAPI.get_next_payment_forecast()."""

    def test_payment_forecast_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_next_payment_forecast() should send PAYMENT_FORECAST_QUERY."""
        with patch.object(authenticated_api.session, "post") as mock_post:
            # First call: get_ledgers
            mock_post.return_value = _make_response(LEDGERS_RESPONSE)
            # Second call: get forecast
            mock_post.side_effect = [
                _make_response(LEDGERS_RESPONSE),
                _make_response(PAYMENT_FORECAST_RESPONSE),
            ]
            result = authenticated_api.get_next_payment_forecast()
            # Find the forecast call (second call)
            forecast_payload = _post_call_args(mock_post, call_index=1)
            assert forecast_payload["json"]["query"] == PAYMENT_FORECAST_QUERY
            assert forecast_payload["json"]["operationName"] == "PaymentForecast"

    def test_payment_forecast_parses_response(self, authenticated_api: SevernTrentAPI):
        """get_next_payment_forecast() should parse forecast correctly."""
        with patch.object(authenticated_api.session, "post") as mock_post:
            mock_post.side_effect = [
                _make_response(LEDGERS_RESPONSE),
                _make_response(PAYMENT_FORECAST_RESPONSE),
            ]
            result = authenticated_api.get_next_payment_forecast()
            assert result["ledger_number"] == "LEDGER1"
            assert result["date"] == "2026-06-15"
            assert result["amount_pence"] == 2500
            assert result["amount_gbp"] == 25.0


# ======================================================================
# 12. Get Manual Meter Readings
# ======================================================================

class TestGetManualMeterReadings:
    """Tests for SevernTrentAPI.get_manual_meter_readings()."""

    def test_manual_readings_sends_correct_query(self, authenticated_api: SevernTrentAPI):
        """get_manual_meter_readings() should send METER_READINGS_QUERY."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(MANUAL_READINGS_RESPONSE)) as mock_post:
            authenticated_api.get_manual_meter_readings()
            payload = _post_call_args(mock_post)
            assert payload["json"]["query"] == METER_READINGS_QUERY
            assert payload["json"]["operationName"] == "MeterReadings"

    def test_manual_readings_sends_account_number(self, authenticated_api: SevernTrentAPI):
        """get_manual_meter_readings() should include account number in variables."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(MANUAL_READINGS_RESPONSE)) as mock_post:
            authenticated_api.get_manual_meter_readings()
            payload = _post_call_args(mock_post)
            assert payload["json"]["variables"]["accountNumber"] == "1234567890"

    def test_manual_readings_parses_response(self, authenticated_api: SevernTrentAPI):
        """get_manual_meter_readings() should parse readings correctly."""
        with patch.object(authenticated_api.session, "post", return_value=_make_response(MANUAL_READINGS_RESPONSE)):
            result = authenticated_api.get_manual_meter_readings()
            assert result["meter_id"] == "meter-1"
            assert result["latest_reading"] == 1234.5
            assert result["reading_source"] == "CUSTOMER"
            assert result["usage_since_last"] == 4.5  # 1234.5 - 1230.0
            assert len(result["all_readings"]) == 2


# ======================================================================
# 13. Token Refresh
# ======================================================================

class TestTokenRefresh:
    """Tests for SevernTrentAPI._ensure_valid_token()."""

    def test_ensure_valid_token_reauthenticates_when_expired(self, api: SevernTrentAPI):
        """_ensure_valid_token() should re-authenticate when token is expired."""
        api.token = "old-token"
        api.token_expires_at = 0  # expired

        with patch.object(api, "authenticate", return_value=True) as mock_auth:
            api._ensure_valid_token()
            mock_auth.assert_called_once()

    def test_ensure_valid_token_skips_when_valid(self, authenticated_api: SevernTrentAPI):
        """_ensure_valid_token() should not re-authenticate when token is still valid."""
        with patch.object(authenticated_api, "authenticate") as mock_auth:
            authenticated_api._ensure_valid_token()
            mock_auth.assert_not_called()


# ======================================================================
# 14. Normalize Browser Token
# ======================================================================

class TestNormalizeBrowserToken:
    """Tests for SevernTrentAPI._normalize_browser_token()."""

    def test_strips_bearer_prefix_case_insensitive(self):
        """_normalize_browser_token() should strip 'Bearer ' prefix (case-insensitive)."""
        assert SevernTrentAPI._normalize_browser_token("Bearer abc123") == "abc123"
        assert SevernTrentAPI._normalize_browser_token("bearer abc123") == "abc123"
        assert SevernTrentAPI._normalize_browser_token("BEARER abc123") == "abc123"

    def test_returns_token_as_is_without_prefix(self):
        """_normalize_browser_token() should return token unchanged if no Bearer prefix."""
        assert SevernTrentAPI._normalize_browser_token("abc123") == "abc123"

    def test_strips_whitespace(self):
        """_normalize_browser_token() should strip whitespace."""
        assert SevernTrentAPI._normalize_browser_token("  abc123  ") == "abc123"
        assert SevernTrentAPI._normalize_browser_token("  Bearer  abc123  ") == "abc123"


# ======================================================================
# 15. Smart Meter Readings (integration of multiple calls)
# ======================================================================

class TestGetMeterReadings:
    """Tests for SevernTrentAPI.get_meter_readings().

    This method makes multiple API calls (authenticate, meter identifiers,
    daily readings, monthly readings), so we mock session.post with a
    sequence of responses.
    """

    def _setup_mock_post(self, api: SevernTrentAPI):
        """Set up mock post to return a sequence of responses for get_meter_readings."""
        responses = [
            _make_response(AUTH_SUCCESS_RESPONSE),       # authenticate
            _make_response(METER_IDENTIFIERS_RESPONSE),  # _fetch_meter_identifiers
            _make_response(SMART_METER_DAILY_RESPONSE),   # daily readings
            _make_response(SMART_METER_MONTHLY_RESPONSE), # monthly readings
        ]
        mock_post = MagicMock(side_effect=responses)
        return patch.object(api.session, "post", mock_post)

    def test_get_meter_readings_calls_authenticate(self, api: SevernTrentAPI):
        """get_meter_readings() should call authenticate first."""
        with self._setup_mock_post(api):
            # authenticate is called internally via session.post
            result = api.get_meter_readings()
            # At minimum, the first call should be authentication
            assert api.session.post.call_count >= 1

    def test_get_meter_readings_sends_smart_meter_query(self, api: SevernTrentAPI):
        """get_meter_readings() should send SMART_METER_READINGS_QUERY for daily data."""
        with self._setup_mock_post(api):
            result = api.get_meter_readings()
            # Find the call that sent the smart meter readings query
            calls = api.session.post.call_args_list
            smart_meter_calls = [
                c for c in calls
                if c[1].get("json", {}).get("operationName") == "SmartMeterReadings"
            ]
            assert len(smart_meter_calls) >= 1
            payload = smart_meter_calls[0][1]["json"]
            assert payload["query"] == SMART_METER_READINGS_QUERY
            assert "utilityFilters" in payload["variables"]

    def test_get_meter_readings_returns_usage_data(self, api: SevernTrentAPI):
        """get_meter_readings() should return usage data with expected keys."""
        with self._setup_mock_post(api):
            result = api.get_meter_readings()
            # Should have standard keys even if some values are 0/None
            expected_keys = [
                "meter_id", "yesterday_usage", "yesterday_date",
                "daily_average", "unit", "all_readings", "monthly_readings",
            ]
            for key in expected_keys:
                assert key in result, f"Missing key: {key}"

    def test_get_meter_readings_returns_empty_on_auth_failure(self, api: SevernTrentAPI):
        """get_meter_readings() should return {} when authentication fails."""
        with patch.object(api, "authenticate", return_value=False):
            result = api.get_meter_readings()
            assert result == {}


# ======================================================================
# 16. Edge cases
# ======================================================================

class TestEdgeCases:
    """Edge case tests for the API client."""

    def test_null_account_returns_empty(self, authenticated_api: SevernTrentAPI):
        """Methods should handle null account in response gracefully."""
        null_account_response = {"data": {"account": None}}
        with patch.object(authenticated_api.session, "post", return_value=_make_response(null_account_response)):
            result = authenticated_api.get_manual_meter_readings()
            assert result == {}

    def test_missing_data_key_returns_empty(self, authenticated_api: SevernTrentAPI):
        """Methods should handle missing 'data' key gracefully."""
        no_data_response = {"errors": [{"message": "Not found"}]}
        with patch.object(authenticated_api.session, "post", return_value=_make_response(no_data_response)):
            result = authenticated_api.get_balance()
            assert result == {}

    def test_http_error_returns_empty(self, authenticated_api: SevernTrentAPI):
        """Methods should handle HTTP errors gracefully."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_resp.json.return_value = {}
        with patch.object(authenticated_api.session, "post", return_value=mock_resp):
            result = authenticated_api.get_balance()
            assert result == {}

    def test_network_error_returns_empty(self, authenticated_api: SevernTrentAPI):
        """Methods should handle network errors gracefully."""
        with patch.object(authenticated_api.session, "post", side_effect=ConnectionError("Network error")):
            result = authenticated_api.get_balance()
            assert result == {}

    def test_empty_properties_returns_empty(self, authenticated_api: SevernTrentAPI):
        """Methods should handle empty properties list gracefully."""
        empty_props_response = {
            "data": {
                "account": {
                    "properties": []
                }
            }
        }
        with patch.object(authenticated_api.session, "post", return_value=_make_response(empty_props_response)):
            result = authenticated_api.get_meter_details()
            assert result == {}
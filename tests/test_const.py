"""Tests for the GraphQL query constants.

These tests validate that each query/mutation constant:
1. Is a valid GraphQL operation (starts with query/mutation keyword)
2. Has the correct operation name matching the constant's intended use
3. Contains the expected fields for the Severn Trent API schema
"""
from __future__ import annotations

import re

import pytest

from custom_components.severn_trent.const import (
    API_URL,
    AUTH_MUTATION,
    API_KEY_MUTATION,
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


# ======================================================================
# API URL
# ======================================================================

class TestApiUrl:
    """Validate the API URL constant."""

    def test_api_url_is_https(self):
        """API URL should use HTTPS."""
        assert API_URL.startswith("https://")

    def test_api_url_is_graphql_endpoint(self):
        """API URL should point to the GraphQL endpoint."""
        assert "graphql" in API_URL

    def test_api_url_is_severn_trent_domain(self):
        """API URL should be on the Severn Trent / Kraken domain."""
        assert "st.kraken.tech" in API_URL


# ======================================================================
# Helper
# ======================================================================

def _extract_operation_type(query: str) -> str:
    """Extract the operation type (query/mutation) from a GraphQL string."""
    stripped = query.strip()
    if stripped.startswith("mutation"):
        return "mutation"
    elif stripped.startswith("query"):
        return "query"
    raise ValueError(f"Unknown operation type in: {stripped[:50]}...")


def _extract_operation_name(query: str) -> str:
    """Extract the operation name from a GraphQL string."""
    # Match patterns like "query OperationName" or "mutation OperationName"
    match = re.match(r"(?:query|mutation)\s+(\w+)", query.strip())
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract operation name from: {query[:80]}...")


# ======================================================================
# Mutations
# ======================================================================

class TestAuthMutation:
    """Validate the AUTH_MUTATION constant."""

    def test_is_mutation(self):
        """AUTH_MUTATION should be a mutation."""
        assert _extract_operation_type(AUTH_MUTATION) == "mutation"

    def test_operation_name(self):
        """AUTH_MUTATION should be named ObtainKrakenToken."""
        assert _extract_operation_name(AUTH_MUTATION) == "ObtainKrakenToken"

    def test_contains_token_fields(self):
        """AUTH_MUTATION should request token and refreshToken fields."""
        assert "token" in AUTH_MUTATION
        assert "refreshToken" in AUTH_MUTATION

    def test_contains_input_variable(self):
        """AUTH_MUTATION should accept an $input variable."""
        assert "$input" in AUTH_MUTATION
        assert "ObtainJSONWebTokenInput" in AUTH_MUTATION


class TestApiKeyMutation:
    """Validate the API_KEY_MUTATION constant."""

    def test_is_mutation(self):
        """API_KEY_MUTATION should be a mutation."""
        assert _extract_operation_type(API_KEY_MUTATION) == "mutation"

    def test_operation_name(self):
        """API_KEY_MUTATION should be named CreateAPIKey."""
        assert _extract_operation_name(API_KEY_MUTATION) == "CreateAPIKey"

    def test_contains_key_field(self):
        """API_KEY_MUTATION should request the key field."""
        assert "key" in API_KEY_MUTATION

    def test_calls_regenerate_secret_key(self):
        """API_KEY_MUTATION should call regenerateSecretKey."""
        assert "regenerateSecretKey" in API_KEY_MUTATION


# ======================================================================
# Queries
# ======================================================================

class TestAccountListQuery:
    """Validate the ACCOUNT_LIST_QUERY constant."""

    def test_is_query(self):
        """ACCOUNT_LIST_QUERY should be a query."""
        assert _extract_operation_type(ACCOUNT_LIST_QUERY) == "query"

    def test_operation_name(self):
        """ACCOUNT_LIST_QUERY should be named AccountNumberList."""
        assert _extract_operation_name(ACCOUNT_LIST_QUERY) == "AccountNumberList"

    def test_contains_viewer_and_accounts(self):
        """ACCOUNT_LIST_QUERY should query viewer.accounts.number."""
        assert "viewer" in ACCOUNT_LIST_QUERY
        assert "accounts" in ACCOUNT_LIST_QUERY
        assert "number" in ACCOUNT_LIST_QUERY


class TestBalanceQuery:
    """Validate the BALANCE_QUERY constant."""

    def test_is_query(self):
        """BALANCE_QUERY should be a query."""
        assert _extract_operation_type(BALANCE_QUERY) == "query"

    def test_operation_name(self):
        """BALANCE_QUERY should be named GetBalance."""
        assert _extract_operation_name(BALANCE_QUERY) == "GetBalance"

    def test_contains_account_and_balance(self):
        """BALANCE_QUERY should query account.balance."""
        assert "account" in BALANCE_QUERY
        assert "balance" in BALANCE_QUERY

    def test_accepts_account_number_variable(self):
        """BALANCE_QUERY should accept $accountNumber variable."""
        assert "$accountNumber" in BALANCE_QUERY


class TestMeterIdentifiersQuery:
    """Validate the METER_IDENTIFIERS_QUERY constant."""

    def test_is_query(self):
        """METER_IDENTIFIERS_QUERY should be a query."""
        assert _extract_operation_type(METER_IDENTIFIERS_QUERY) == "query"

    def test_operation_name(self):
        """METER_IDENTIFIERS_QUERY should be named GetMeterIdentifiers."""
        assert _extract_operation_name(METER_IDENTIFIERS_QUERY) == "GetMeterIdentifiers"

    def test_contains_meter_fields(self):
        """METER_IDENTIFIERS_QUERY should request meter identifiers."""
        assert "meterPointReference" in METER_IDENTIFIERS_QUERY
        assert "serialNumber" in METER_IDENTIFIERS_QUERY
        assert "capabilityType" in METER_IDENTIFIERS_QUERY

    def test_queries_active_water_meters(self):
        """METER_IDENTIFIERS_QUERY should query activeWaterMeters."""
        assert "activeWaterMeters" in METER_IDENTIFIERS_QUERY


class TestMeterReadingsQuery:
    """Validate the METER_READINGS_QUERY constant."""

    def test_is_query(self):
        """METER_READINGS_QUERY should be a query."""
        assert _extract_operation_type(METER_READINGS_QUERY) == "query"

    def test_operation_name(self):
        """METER_READINGS_QUERY should be named MeterReadings."""
        assert _extract_operation_name(METER_READINGS_QUERY) == "MeterReadings"

    def test_contains_reading_fields(self):
        """METER_READINGS_QUERY should request reading value, date, and source."""
        assert "valueCubicMetres" in METER_READINGS_QUERY
        assert "readingDate" in METER_READINGS_QUERY
        assert "source" in METER_READINGS_QUERY


class TestSmartMeterReadingsQuery:
    """Validate the SMART_METER_READINGS_QUERY constant."""

    def test_is_query(self):
        """SMART_METER_READINGS_QUERY should be a query."""
        assert _extract_operation_type(SMART_METER_READINGS_QUERY) == "query"

    def test_operation_name(self):
        """SMART_METER_READINGS_QUERY should be named SmartMeterReadings."""
        assert _extract_operation_name(SMART_METER_READINGS_QUERY) == "SmartMeterReadings"

    def test_contains_measurement_fields(self):
        """SMART_METER_READINGS_QUERY should request measurements with value and unit."""
        assert "measurements" in SMART_METER_READINGS_QUERY
        assert "value" in SMART_METER_READINGS_QUERY
        assert "unit" in SMART_METER_READINGS_QUERY

    def test_accepts_utility_filters(self):
        """SMART_METER_READINGS_QUERY should accept $utilityFilters variable."""
        assert "$utilityFilters" in SMART_METER_READINGS_QUERY
        assert "UtilityFiltersInput" in SMART_METER_READINGS_QUERY

    def test_contains_interval_fields(self):
        """SMART_METER_READINGS_QUERY should include startAt/endAt on IntervalMeasurementType."""
        assert "startAt" in SMART_METER_READINGS_QUERY
        assert "endAt" in SMART_METER_READINGS_QUERY


class TestPaymentScheduleQuery:
    """Validate the PAYMENT_SCHEDULE_QUERY constant."""

    def test_is_query(self):
        """PAYMENT_SCHEDULE_QUERY should be a query."""
        assert _extract_operation_type(PAYMENT_SCHEDULE_QUERY) == "query"

    def test_operation_name(self):
        """PAYMENT_SCHEDULE_QUERY should be named CurrentActivePaymentSchedule."""
        assert _extract_operation_name(PAYMENT_SCHEDULE_QUERY) == "CurrentActivePaymentSchedule"

    def test_contains_payment_fields(self):
        """PAYMENT_SCHEDULE_QUERY should request payment schedule fields."""
        assert "paymentDay" in PAYMENT_SCHEDULE_QUERY
        assert "paymentAmount" in PAYMENT_SCHEDULE_QUERY
        assert "paymentFrequency" in PAYMENT_SCHEDULE_QUERY


class TestMeterDetailsQuery:
    """Validate the METER_DETAILS_QUERY constant."""

    def test_is_query(self):
        """METER_DETAILS_QUERY should be a query."""
        assert _extract_operation_type(METER_DETAILS_QUERY) == "query"

    def test_operation_name(self):
        """METER_DETAILS_QUERY should be named MeterDetails."""
        assert _extract_operation_name(METER_DETAILS_QUERY) == "MeterDetails"

    def test_contains_meter_detail_fields(self):
        """METER_DETAILS_QUERY should request numberOfDigits and readings."""
        assert "numberOfDigits" in METER_DETAILS_QUERY
        assert "serialNumber" in METER_DETAILS_QUERY
        assert "readings" in METER_DETAILS_QUERY


class TestOutstandingPaymentQuery:
    """Validate the OUTSTANDING_PAYMENT_QUERY constant."""

    def test_is_query(self):
        """OUTSTANDING_PAYMENT_QUERY should be a query."""
        assert _extract_operation_type(OUTSTANDING_PAYMENT_QUERY) == "query"

    def test_operation_name(self):
        """OUTSTANDING_PAYMENT_QUERY should be named OutstandingPayment."""
        assert _extract_operation_name(OUTSTANDING_PAYMENT_QUERY) == "OutstandingPayment"

    def test_contains_payments_outstanding(self):
        """OUTSTANDING_PAYMENT_QUERY should request paymentsOutstanding."""
        assert "paymentsOutstanding" in OUTSTANDING_PAYMENT_QUERY


class TestRateLimitQuery:
    """Validate the RATE_LIMIT_QUERY constant."""

    def test_is_query(self):
        """RATE_LIMIT_QUERY should be a query."""
        assert _extract_operation_type(RATE_LIMIT_QUERY) == "query"

    def test_operation_name(self):
        """RATE_LIMIT_QUERY should be named apiRateLimitInfo."""
        assert _extract_operation_name(RATE_LIMIT_QUERY) == "apiRateLimitInfo"

    def test_contains_rate_limit_fields(self):
        """RATE_LIMIT_QUERY should request rate limit fields."""
        assert "pointsAllowanceRateLimit" in RATE_LIMIT_QUERY
        assert "isBlocked" in RATE_LIMIT_QUERY
        assert "remainingPoints" in RATE_LIMIT_QUERY


class TestLedgersQuery:
    """Validate the LEDGERS_QUERY constant."""

    def test_is_query(self):
        """LEDGERS_QUERY should be a query."""
        assert _extract_operation_type(LEDGERS_QUERY) == "query"

    def test_operation_name(self):
        """LEDGERS_QUERY should be named Ledgers."""
        assert _extract_operation_name(LEDGERS_QUERY) == "Ledgers"

    def test_contains_ledger_fields(self):
        """LEDGERS_QUERY should request number and ledgerType."""
        assert "number" in LEDGERS_QUERY
        assert "ledgerType" in LEDGERS_QUERY


class TestPaymentForecastQuery:
    """Validate the PAYMENT_FORECAST_QUERY constant."""

    def test_is_query(self):
        """PAYMENT_FORECAST_QUERY should be a query."""
        assert _extract_operation_type(PAYMENT_FORECAST_QUERY) == "query"

    def test_operation_name(self):
        """PAYMENT_FORECAST_QUERY should be named PaymentForecast."""
        assert _extract_operation_name(PAYMENT_FORECAST_QUERY) == "PaymentForecast"

    def test_contains_forecast_fields(self):
        """PAYMENT_FORECAST_QUERY should request date and amount."""
        assert "date" in PAYMENT_FORECAST_QUERY
        assert "amount" in PAYMENT_FORECAST_QUERY

    def test_accepts_ledger_number_variable(self):
        """PAYMENT_FORECAST_QUERY should accept $ledgerNumber variable."""
        assert "$ledgerNumber" in PAYMENT_FORECAST_QUERY
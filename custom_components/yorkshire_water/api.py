"""Async API client for Yorkshire Water."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import logging
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import (
    YORKSHIRE_WATER_API_BASE_URL,
    YORKSHIRE_WATER_CURRENT_CONSUMPTION_ENDPOINT_PATH,
    YORKSHIRE_WATER_CURRENT_CONSUMPTION_PATH,
    YORKSHIRE_WATER_DAILY_CONSUMPTION_ENDPOINT_PATH,
    YORKSHIRE_WATER_DAILY_CONSUMPTION_PATH,
    YORKSHIRE_WATER_METER_DETAILS_ENDPOINT_PATH,
    YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH,
    YORKSHIRE_WATER_SMART_METER_API_BASE_URL,
    YORKSHIRE_WATER_TOKEN_ENDPOINT,
    YORKSHIRE_WATER_YOUR_USAGE_ENDPOINT_PATH,
)

_LOGGER = logging.getLogger(__name__)

_REDACTED = "<redacted>"
_SENSITIVE_KEYS = {
    "account",
    "account_id",
    "accountid",
    "account_number",
    "account_reference",
    "accountreference",
    "authorization",
    "authorization_code",
    "bearer",
    "bearer_token",
    "bearertoken",
    "code",
    "code_verifier",
    "codeverifier",
    "cookie",
    "customer",
    "customer_id",
    "customerid",
    "customer_reference",
    "customerreference",
    "id_token",
    "meter",
    "meter_id",
    "meterid",
    "meter_reference",
    "meterreference",
    "mprn",
    "refresh_token",
    "serial_number",
    "session_id",
    "sessionid",
    "set_cookie",
    "set-cookie",
    "session",
    "token",
}


class YorkshireWaterError(Exception):
    """Base error for Yorkshire Water API failures."""


class YorkshireWaterAuthError(YorkshireWaterError):
    """Authentication or authorization failed."""


class YorkshireWaterExpiredSessionError(YorkshireWaterAuthError):
    """Session token has expired."""


class YorkshireWaterAccountNotFoundError(YorkshireWaterError):
    """The configured account could not be found."""


class YorkshireWaterMeterNotFoundError(YorkshireWaterError):
    """The configured meter could not be found."""


class YorkshireWaterNoSmartMeterDataError(YorkshireWaterError):
    """No smart meter data is available for the configured meter."""


class YorkshireWaterRateLimitError(YorkshireWaterError):
    """Yorkshire Water rate limited the request."""


class YorkshireWaterUpstreamUnavailableError(YorkshireWaterError):
    """Yorkshire Water upstream service is temporarily unavailable."""


class YorkshireWaterSchemaError(YorkshireWaterError):
    """The response schema did not match what the integration expects."""


class YorkshireWaterEndpointNotConfiguredError(YorkshireWaterError):
    """Yorkshire Water endpoint details have not been captured yet."""


def parse_token_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse OAuth token response metadata without returning raw token values."""
    _ensure_dict(data, "Token response payload")

    expires_in = data.get("expires_in")
    try:
        expires_in_seconds = int(expires_in)
    except (TypeError, ValueError) as err:
        raise YorkshireWaterSchemaError("Token response expires_in was not an integer") from err

    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
    scope = data.get("scope")

    return {
        "has_id_token": bool(data.get("id_token")),
        "has_access_token": bool(data.get("access_token")),
        "expires_in": expires_in_seconds,
        "expires_at": expires_at.isoformat(),
        "token_type": data.get("token_type"),
        "scope": scope.split() if isinstance(scope, str) else [],
    }


def parse_account_discovery_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a redacted account discovery response into a normalized shape."""
    _ensure_dict(data, "Account discovery payload")

    # TODO: Replace these scaffold mappings once captured Yorkshire Water
    # schemas confirm the real account and property fields.
    accounts = data.get("accounts")
    if accounts is None:
        return []
    if not isinstance(accounts, list):
        raise YorkshireWaterSchemaError("Account discovery payload accounts was not a list")

    normalized: list[dict[str, Any]] = []
    customer = data.get("customer") or {}
    if not isinstance(customer, dict):
        raise YorkshireWaterSchemaError("Account discovery customer section was not an object")
    customer_id = _first_present(customer, "customerId", "customer_id")
    for item in accounts:
        if not isinstance(item, dict):
            raise YorkshireWaterSchemaError("Account discovery item was not an object")
        normalized.append(
            {
                "account_id": _first_present(item, "accountId", "account_id"),
                "customer_id": customer_id,
                "property_id": _first_present(item, "propertyId", "property_id"),
            }
        )
    return normalized


def parse_meter_discovery_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a redacted meter discovery response into a normalized shape."""
    _ensure_response_shape("meter_details", data, dict)

    if "accountReference" in data or "meterReference" in data:
        return [
            {
                "account_reference": data.get("accountReference"),
                "meter_reference": data.get("meterReference"),
                "start_date": _parse_optional_datetime(data.get("startDate")),
                "end_date": _parse_optional_datetime(data.get("endDate")),
                "current_date": _parse_optional_datetime(data.get("currentDate")),
            }
        ]

    # TODO: Remove this earlier scaffold shape once all discovery fixtures use
    # confirmed Yorkshire Water schemas.
    meters = data.get("meters")
    if meters is None:
        return []
    if not isinstance(meters, list):
        raise YorkshireWaterSchemaError("Meter discovery payload meters was not a list")

    normalized: list[dict[str, Any]] = []
    for item in meters:
        if not isinstance(item, dict):
            raise YorkshireWaterSchemaError("Meter discovery item was not an object")
        normalized.append(
            {
                "meter_id": _first_present(item, "meterId", "meter_id"),
                "meter_type": _first_present(item, "meterType", "meter_type"),
                "status": item.get("status"),
                "unit": _first_present(item, "unit", "uom", "unitOfMeasure"),
            }
        )
    return normalized


def parse_account_summary_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse only safe account status metadata from an account summary payload."""
    _ensure_dict(data, "Account summary payload")

    return {
        "account_reference": data.get("accountReference"),
        "display_account_reference": data.get("displayAccountReference"),
        "account_status": data.get("accountStatus"),
        "is_closed": data.get("isClosed"),
        "is_metered": data.get("isMetered"),
        "is_ready_for_reading": data.get("isReadyForReading"),
        "account_start_date": _parse_optional_datetime(data.get("accountStartDate")),
        "account_end_date": _parse_optional_datetime(data.get("accountEndDate")),
    }


def parse_current_consumption_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse a redacted current consumption response into a normalized shape."""
    _ensure_response_shape("current_consumption", data, dict)

    # TODO: Replace these scaffold mappings once captured Yorkshire Water
    # schemas confirm whether this endpoint is a reading, consumption total, or
    # another portal-specific summary.
    current = data.get("currentConsumption") or data.get("current") or {}
    if not isinstance(current, dict):
        raise YorkshireWaterSchemaError("Current consumption payload section was not an object")

    value = _first_present(current, "meterReading", "meter_reading", "reading")
    unit = _first_present(current, "unit", "uom", "unitOfMeasure") or "m3"
    reading = _normalise_optional_volume(value, unit)

    return {
        "meter_reading_m3": round(reading, 3) if reading is not None else None,
        "estimated": current.get("estimated"),
        "reading_date": _first_present(current, "readingDate", "reading_date"),
        "continuous_flow_alarm": _first_present(
            current,
            "continuousFlowAlarm",
            "continuous_flow_alarm",
            "continuousFlowStatus",
            "continuous_flow_status",
        ),
        "data_latest_update_status": _first_present(
            current,
            "dataLatestUpdateStatus",
            "latest_update_status",
        ),
    }


JsonPayload = dict[str, Any] | list[Any]


def parse_daily_consumption_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a redacted daily consumption response into normalized periods."""
    _ensure_response_shape("your_usage", data, dict)

    raw_items = data.get("dailyUsageData")
    if raw_items is None:
        return []
    if not isinstance(raw_items, list):
        raise YorkshireWaterSchemaError(
            "Unexpected Yorkshire Water response shape for your_usage: "
            f"{_json_type_name(raw_items)}"
        )

    return [_daily_usage_item_to_period(item) for item in raw_items]


def parse_daily_consumption_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Parse daily consumption response totals and normalized periods."""
    _ensure_response_shape("daily_consumption", data, dict)
    periods = [
        _period_from_normalized_dict(item)
        for item in parse_daily_consumption_response(data)
    ]
    return {
        "daily_periods": periods,
        "included_day_count": len(periods),
        "total_litres": _coerce_optional_float(data.get("totalLitres")),
        "total_cost": _coerce_optional_float(data.get("totalCost")),
        "clean_water_cost": _coerce_optional_float(
            data.get("totalStandardTariffCleanWaterCost")
        ),
        "sewerage_cost": _coerce_optional_float(data.get("totalStandardTariffSewerageCost")),
        "daily_litres_average": _coerce_optional_float(data.get("dailyLitresAverage")),
        "daily_cost_average_for_year": _coerce_optional_float(
            data.get("dailyCostAverageForYear")
        ),
    }


def _daily_usage_item_to_period(item: Any) -> dict[str, Any]:
    """Normalize one daily usage row."""
    if not isinstance(item, dict):
        raise YorkshireWaterSchemaError(
            "Unexpected Yorkshire Water response shape for your_usage: "
            f"{_json_type_name(item)}"
        )
    start_value = _first_present(item, "startDate", "start_date", "date")
    end_value = _first_present(item, "endDate", "end_date") or start_value
    value = _first_present(
        item,
        "totalConsumptionLitres",
        "total_consumption_litres",
        "value",
        "usage",
        "consumption",
    )
    unit = _first_present(item, "unit", "uom", "unitOfMeasure") or (
        "litres"
        if _first_present(item, "totalConsumptionLitres", "total_consumption_litres")
        is not None
        else "m3"
    )
    volume = _normalise_optional_volume(value, unit)
    return {
        "start": _parse_date(start_value).isoformat() if start_value else None,
        "end": _parse_date(end_value).isoformat() if end_value else None,
        "value_m3": round(volume, 3) if volume is not None else None,
        "estimated": _first_present(
            item,
            "isEstimatedConsumption",
            "is_estimated_consumption",
            "estimated",
            "isEstimated",
            "is_estimated",
        ),
        "missing": _first_present(
            item,
            "isMissingConsumption",
            "is_missing_consumption",
            "missing",
            "isMissing",
            "is_missing",
        ),
        "continuous_flow_alarm": _first_present(
            item,
            "continuousFlowAlarm",
            "continuous_flow_alarm",
        ),
        "estimated_day_count": _first_present(
            item,
            "estimatedDayCount",
            "estimated_day_count",
        ),
        "missing_day_count": _first_present(
            item,
            "missingDayCount",
            "missing_day_count",
        ),
        "source": item.get("source"),
        "freshness": item.get("lastUpdated"),
        "total_cost": _first_present(
            item,
            "totalCostIncludingSewerage",
            "total_cost_including_sewerage",
            "totalCost",
            "total_cost",
        ),
        "clean_water_cost": _first_present(
            item,
            "standardTariffCleanWaterCost",
            "standard_tariff_clean_water_cost",
            "cleanWaterCost",
            "clean_water_cost",
        ),
        "sewerage_cost": _first_present(
            item,
            "standardTariffSewerageCost",
            "standard_tariff_sewerage_cost",
            "sewerageCost",
            "sewerage_cost",
        ),
    }


def parse_monthly_consumption_response(data: JsonPayload) -> list[dict[str, Any]]:
    """Parse monthly consumption from a list response or monthlyConsumption object."""
    if isinstance(data, list):
        raw_items = data
    else:
        _ensure_response_shape("monthly_usage", data, dict)
        raw_items = data.get("monthlyConsumption")
        if raw_items is None:
            return []
    if not isinstance(raw_items, list):
        raise YorkshireWaterSchemaError(
            "Unexpected Yorkshire Water response shape for monthly_usage: "
            f"{_json_type_name(raw_items)}"
        )

    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise YorkshireWaterSchemaError(
                "Unexpected Yorkshire Water response shape for monthly_usage: "
                f"{_json_type_name(item)}"
            )
        normalized.append(_period_from_payload(item))
    return normalized


def parse_yearly_consumption_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse yearly usage from an object containing monthlyConsumption."""
    _ensure_response_shape("yearly_usage", data, dict)
    raw_items = data.get("monthlyConsumption")
    if raw_items is None:
        return []
    if not isinstance(raw_items, list):
        raise YorkshireWaterSchemaError(
            "Unexpected Yorkshire Water response shape for yearly_usage: "
            f"{_json_type_name(raw_items)}"
        )

    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise YorkshireWaterSchemaError(
                "Unexpected Yorkshire Water response shape for yearly_usage: "
                f"{_json_type_name(item)}"
            )
        normalized.append(_period_from_payload(item))
    return normalized


def parse_meter_reading_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse a redacted meter reading response into a normalized shape."""
    _ensure_dict(data, "Meter reading payload")

    # TODO: Replace these scaffold mappings once captured Yorkshire Water
    # schemas confirm the real meter reading endpoint and units.
    reading_data = data.get("meterReading") or data.get("reading") or {}
    if not isinstance(reading_data, dict):
        raise YorkshireWaterSchemaError("Meter reading payload section was not an object")

    value = _first_present(reading_data, "reading", "meterReading", "meter_reading")
    unit = _first_present(reading_data, "unit", "uom", "unitOfMeasure") or "m3"
    reading = _normalise_optional_volume(value, unit)

    return {
        "meter_reading_m3": round(reading, 3) if reading is not None else None,
        "estimated": reading_data.get("estimated"),
        "reading_date": _first_present(reading_data, "readingDate", "reading_date"),
        "source": reading_data.get("source"),
    }


def parse_api_error_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse a redacted API error response into a structured discovery error."""
    _ensure_dict(data, "API error payload")

    # TODO: Replace these scaffold mappings once captured Yorkshire Water error
    # payloads confirm the real error envelope.
    error = data.get("error") or data
    if not isinstance(error, dict):
        raise YorkshireWaterSchemaError("API error payload section was not an object")

    return {
        "code": _first_present(error, "code", "errorCode", "error_code"),
        "message": _first_present(error, "message", "detail", "title"),
        "status": data.get("status"),
    }


@dataclass(slots=True)
class UsagePeriod:
    """Water usage for a period."""

    start: date
    end: date
    value: float
    unit: str
    source: str | None = None
    freshness: str | None = None

    @property
    def cubic_metres(self) -> float:
        """Return the usage value in cubic metres."""
        normalised = self.unit.lower().replace("³", "3").replace(" ", "")
        if normalised in {"m3", "cubicmetres", "cubicmeters"}:
            return self.value
        if normalised in {"l", "litre", "litres", "liter", "liters"}:
            return self.value / 1000
        raise YorkshireWaterSchemaError(f"Unsupported water unit: {self.unit}")


class YorkshireWaterAPI:
    """Provider-specific Yorkshire Water portal client.

    The Home Assistant integration is intentionally separated from this client.
    TODO: Capture Yorkshire Water's live portal auth and consumption endpoints,
    then implement the endpoint-specific request/response handling here.
    """

    def __init__(
        self,
        session: ClientSession,
        session_token: str | None,
        account_id: str | None = None,
        meter_id: str | None = None,
        bearer_token: str | None = None,
        account_reference: str | None = None,
        meter_reference: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._session_token = (bearer_token or session_token or "").strip()
        self.account_id = (account_reference or account_id or "").strip() or None
        self.meter_id = (meter_reference or meter_id or "").strip() or None
        self.account_reference = self.account_id
        self.meter_reference = self.meter_id

    @staticmethod
    def redact(value: Any) -> Any:
        """Return a recursively redacted value safe for debug logs."""
        if isinstance(value, dict):
            return {
                key: _REDACTED
                if str(key).lower().replace("-", "_") in _SENSITIVE_KEYS
                else YorkshireWaterAPI.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [YorkshireWaterAPI.redact(item) for item in value]
        if isinstance(value, str) and value.lower().startswith("bearer "):
            return _REDACTED
        return value

    async def async_exchange_authorization_code(
        self,
        authorization_code: str,
        code_verifier: str,
        *,
        redirect_uri: str = "https://my.yorkshirewater.com/account/callback/response",
        client_id: str = "css-onlineaccount-fe",
    ) -> dict[str, Any]:
        """Placeholder for the discovered OAuth authorization-code exchange.

        TODO: Implement once token response handling and Home Assistant config
        flow storage are designed. Do not log raw authorization codes, code
        verifiers, access tokens, refresh tokens, or cookies.
        """
        form_shape = {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": authorization_code,
            "code_verifier": code_verifier,
        }
        _LOGGER.debug(
            "Yorkshire Water token route discovered: endpoint=%s content_type=%s form=%s",
            YORKSHIRE_WATER_TOKEN_ENDPOINT,
            "application/x-www-form-urlencoded",
            self.redact(form_shape),
        )
        raise YorkshireWaterEndpointNotConfiguredError(
            "Yorkshire Water OAuth token exchange is discovered but not implemented yet"
        )

    async def async_get_meter_details(self, account_reference: str) -> dict[str, Any]:
        """Fetch meter details for an account reference."""
        payload = await self._async_request_json(
            "GET",
            YORKSHIRE_WATER_METER_DETAILS_ENDPOINT_PATH,
            endpoint_label="meter_details",
            params={"accountReference": account_reference},
        )
        _ensure_response_shape("meter_details", payload, dict)
        meters = parse_meter_discovery_response(payload)
        if meters:
            first_meter = meters[0]
            self.account_reference = first_meter.get("account_reference") or account_reference
            self.account_id = self.account_reference
            self.meter_reference = first_meter.get("meter_reference") or self.meter_reference
            self.meter_id = self.meter_reference
        return {"raw": payload, "meters": meters}

    async def async_get_current_consumption(self, meter_reference: str) -> dict[str, Any]:
        """Fetch current consumption for a meter reference."""
        payload = await self._async_request_json(
            "GET",
            YORKSHIRE_WATER_CURRENT_CONSUMPTION_ENDPOINT_PATH,
            endpoint_label="current_consumption",
            params={"meterReference": meter_reference},
        )
        _ensure_response_shape("current_consumption", payload, dict)
        return parse_current_consumption_response(payload)

    async def async_get_your_usage(self, meter_reference: str) -> JsonPayload:
        """Fetch usage history for a meter reference."""
        payload = await self._async_request_json(
            "GET",
            YORKSHIRE_WATER_YOUR_USAGE_ENDPOINT_PATH,
            endpoint_label="your_usage",
            params={"meterReference": meter_reference},
        )
        _ensure_response_shape("your_usage", payload, (dict, list))
        return payload

    async def async_get_daily_consumption(
        self,
        meter_reference: str,
        *,
        start_date: date | str,
        end_date: date | str,
        move_in_date: date | str,
        move_out_date: date | str,
        time_period: int = 1,
    ) -> dict[str, Any]:
        """Fetch daily consumption for a meter reference."""
        payload = await self._async_request_json(
            "GET",
            YORKSHIRE_WATER_DAILY_CONSUMPTION_ENDPOINT_PATH,
            endpoint_label="daily_consumption",
            params={
                "meterReference": meter_reference,
                "startDate": _date_param(start_date),
                "endDate": _date_param(end_date),
                "moveInDate": _date_param(move_in_date),
                "moveOutDate": _date_param(move_out_date),
                "timePeriod": time_period,
            },
        )
        _ensure_response_shape("daily_consumption", payload, dict)
        summary = parse_daily_consumption_summary(payload)
        _LOGGER.debug(
            "Yorkshire Water API parsed: daily_consumption daily_row_count=%s",
            len(summary["daily_periods"]),
        )
        return summary

    async def async_fetch_usage_summary(self, today: date | None = None) -> dict[str, Any]:
        """Fetch and summarize current Yorkshire Water usage data."""
        if not self._session_token:
            raise YorkshireWaterEndpointNotConfiguredError(
                "Yorkshire Water bearer token is not configured yet"
            )

        meter_reference = self.meter_reference
        meter_details: list[dict[str, Any]] = []
        move_in_date: date | str | None = None
        move_out_date: date | str | None = None
        if not meter_reference and self.account_reference:
            meter_payload = await self.async_get_meter_details(self.account_reference)
            meter_details = meter_payload.get("meters", [])
            if meter_details:
                meter_reference = meter_details[0].get("meter_reference")
                move_in_date = meter_details[0].get("start_date")
                move_out_date = meter_details[0].get("end_date")

        if not meter_reference:
            raise YorkshireWaterEndpointNotConfiguredError(
                "Yorkshire Water meter reference is not configured yet"
            )

        current_reading = await self.async_get_current_consumption(meter_reference)
        today = today or date.today()
        month_start = today.replace(day=1)
        daily_summary = await self.async_get_daily_consumption(
            meter_reference,
            start_date=month_start,
            end_date=today,
            move_in_date=move_in_date or month_start,
            move_out_date=move_out_date or today,
        )
        usage_payload = await self.async_get_your_usage(meter_reference)
        daily_periods = daily_summary["daily_periods"]
        monthly_periods = _extract_usage_periods(usage_payload, "monthly")
        yearly_periods = _extract_usage_periods(usage_payload, "yearly")

        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())
        previous_week_start = week_start - timedelta(days=7)
        previous_week_end = week_start - timedelta(days=1)
        year_start = today.replace(month=1, day=1)

        by_start = {period["start_date"]: period for period in daily_periods}
        recent_periods = sorted(
            daily_periods,
            key=lambda item: item["start_date"],
            reverse=True,
        )
        last_seven = sorted(
            [
                period
                for period in daily_periods
                if period["value_litres"] is not None
                and period["start_date"] <= yesterday
            ],
            key=lambda item: item["start_date"],
        )[-7:]
        week_end = min(
            today,
            max((period["start_date"] for period in daily_periods), default=today),
        )
        week_periods = [
            period
            for period in daily_periods
            if week_start <= period["start_date"] <= week_end
        ]

        def sum_range(start: date, end: date) -> float | None:
            values = [
                period["value_litres"]
                for period in daily_periods
                if period["value_litres"] is not None
                and start <= period["start_date"] <= end
            ]
            if not values:
                return None
            return round(sum(values), 2)

        yesterday_period = by_start.get(yesterday)
        today_period = by_start.get(today)
        latest_period = max(daily_periods, key=lambda item: item["end_date"], default=None)
        yesterday_periods = [yesterday_period] if yesterday_period else []
        today_periods = [today_period] if today_period else []
        previous_week_periods = [
            period
            for period in daily_periods
            if previous_week_start <= period["start_date"] <= previous_week_end
        ]
        month_periods = [
            period for period in daily_periods if month_start <= period["start_date"] <= today
        ]
        estimated_day_count = _sum_period_count(
            daily_periods,
            "estimated_day_count",
        ) or _count_period_flag(daily_periods, "estimated")
        missing_day_count = _sum_period_count(
            daily_periods,
            "missing_day_count",
        ) or _count_period_flag(daily_periods, "missing")
        latest_update = _find_first_key(
            usage_payload,
            "latestUpdateDate",
            "latest_update_date",
            "lastUpdated",
            "last_updated",
        )
        latest_data_status = _first_non_none(
            _first_present(
                current_reading,
                "data_latest_update_status",
                "dataLatestUpdateStatus",
                "latest_update_status",
            ),
            _first_present(
                usage_payload if isinstance(usage_payload, dict) else {},
                "dataLatestUpdateStatus",
                "latest_update_status",
                "status",
            ),
            f"current_to_{latest_period['end']}" if latest_period else None,
        )
        year_to_date_periods = yearly_periods
        year_to_date_litres = _total_from_periods(year_to_date_periods)

        return {
            "daily_periods": [_usage_period_as_dict(period) for period in recent_periods],
            "monthly_periods": [_usage_period_as_dict(period) for period in monthly_periods],
            "yearly_periods": [_usage_period_as_dict(period) for period in yearly_periods],
            "yesterday_periods": [_usage_period_as_dict(period) for period in yesterday_periods],
            "yesterday_usage_litres": yesterday_period.get("value_litres")
            if yesterday_period
            else None,
            "yesterday_start": yesterday.isoformat(),
            "yesterday_end": yesterday.isoformat(),
            "yesterday_included_day_count": len(yesterday_periods),
            "yesterday_estimated_day_count": _count_period_flag(yesterday_periods, "estimated"),
            "yesterday_missing_day_count": _count_period_flag(yesterday_periods, "missing"),
            "yesterday_total_cost": _sum_period_field(yesterday_periods, "total_cost"),
            "yesterday_clean_water_cost": _sum_period_field(
                yesterday_periods,
                "clean_water_cost",
            ),
            "yesterday_sewerage_cost": _sum_period_field(yesterday_periods, "sewerage_cost"),
            "today_periods": [_usage_period_as_dict(period) for period in today_periods],
            "today_usage_litres": today_period.get("value_litres") if today_period else None,
            "today_start": today.isoformat(),
            "today_end": today.isoformat(),
            "today_status_detail": None
            if today_period
            else f"latest_available_usage_data_is_{latest_period['end']}"
            if latest_period
            else "usage_data_unavailable",
            "today_included_day_count": len(today_periods),
            "today_estimated_day_count": _count_period_flag(today_periods, "estimated"),
            "today_missing_day_count": _count_period_flag(today_periods, "missing"),
            "today_total_cost": _sum_period_field(today_periods, "total_cost"),
            "today_clean_water_cost": _sum_period_field(today_periods, "clean_water_cost"),
            "today_sewerage_cost": _sum_period_field(today_periods, "sewerage_cost"),
            "daily_average_periods": [_usage_period_as_dict(period) for period in last_seven],
            "daily_average_litres": round(
                sum(period["value_litres"] for period in last_seven)
                / len(last_seven),
                2,
            )
            if last_seven
            else None,
            "daily_average_period_start": last_seven[0]["start"] if last_seven else None,
            "daily_average_period_end": last_seven[-1]["end"] if last_seven else None,
            "daily_average_included_day_count": len(last_seven),
            "daily_average_estimated_day_count": _count_period_flag(last_seven, "estimated"),
            "daily_average_missing_day_count": _count_period_flag(last_seven, "missing"),
            "daily_average_total_cost": _sum_period_field(last_seven, "total_cost"),
            "daily_average_clean_water_cost": _sum_period_field(last_seven, "clean_water_cost"),
            "daily_average_sewerage_cost": _sum_period_field(last_seven, "sewerage_cost"),
            "week_to_date_periods": [_usage_period_as_dict(period) for period in week_periods],
            "week_to_date_litres": _total_from_periods(week_periods),
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "week_to_date_included_day_count": len(week_periods),
            "week_to_date_estimated_day_count": _count_period_flag(week_periods, "estimated"),
            "week_to_date_missing_day_count": _count_period_flag(week_periods, "missing"),
            "week_to_date_total_cost": _sum_period_field(week_periods, "total_cost"),
            "week_to_date_clean_water_cost": _sum_period_field(
                week_periods,
                "clean_water_cost",
            ),
            "week_to_date_sewerage_cost": _sum_period_field(week_periods, "sewerage_cost"),
            "previous_week_periods": [
                _usage_period_as_dict(period) for period in previous_week_periods
            ],
            "previous_week_litres": sum_range(previous_week_start, previous_week_end),
            "previous_week_start": previous_week_start.isoformat(),
            "previous_week_end": previous_week_end.isoformat(),
            "previous_week_included_day_count": len(previous_week_periods),
            "previous_week_estimated_day_count": _count_period_flag(
                previous_week_periods,
                "estimated",
            ),
            "previous_week_missing_day_count": _count_period_flag(
                previous_week_periods,
                "missing",
            ),
            "previous_week_total_cost": _sum_period_field(previous_week_periods, "total_cost"),
            "previous_week_clean_water_cost": _sum_period_field(
                previous_week_periods,
                "clean_water_cost",
            ),
            "previous_week_sewerage_cost": _sum_period_field(
                previous_week_periods,
                "sewerage_cost",
            ),
            "month_to_date_periods": [_usage_period_as_dict(period) for period in month_periods],
            "month_to_date_litres": _first_non_none(
                daily_summary.get("total_litres"),
                _monthly_total_for_month(monthly_periods, today),
                sum_range(month_start, today),
            ),
            "month_start": month_start.isoformat(),
            "month_to_date_included_day_count": daily_summary.get("included_day_count"),
            "month_to_date_estimated_day_count": estimated_day_count,
            "month_to_date_missing_day_count": missing_day_count,
            "month_to_date_total_cost": daily_summary.get("total_cost"),
            "month_to_date_clean_water_cost": daily_summary.get("clean_water_cost"),
            "month_to_date_sewerage_cost": daily_summary.get("sewerage_cost"),
            "year_to_date_periods": [
                _usage_period_as_dict(period) for period in year_to_date_periods
            ],
            "year_to_date_litres": year_to_date_litres,
            "year_start": year_start.isoformat(),
            "year_to_date_included_day_count": len(year_to_date_periods)
            if year_to_date_litres is not None
            else None,
            "year_to_date_estimated_day_count": _sum_period_count(
                year_to_date_periods,
                "estimated_day_count",
            )
            if year_to_date_litres is not None
            else None,
            "year_to_date_missing_day_count": _sum_period_count(
                year_to_date_periods,
                "missing_day_count",
            )
            if year_to_date_litres is not None
            else None,
            "year_to_date_total_cost": _sum_period_field(year_to_date_periods, "total_cost"),
            "year_to_date_clean_water_cost": _sum_period_field(
                year_to_date_periods,
                "clean_water_cost",
            ),
            "year_to_date_sewerage_cost": _sum_period_field(
                year_to_date_periods,
                "sewerage_cost",
            ),
            "meter_reading_m3": None,
            "meter_reading_estimated": None,
            "meter_reading_date": None,
            "meter_reading_status": "not_implemented",
            "continuous_flow_alarm": _first_non_none(
                _first_present(
                    current_reading,
                    "continuous_flow_alarm",
                    "continuousFlowAlarm",
                    "continuous_flow",
                ),
                _any_period_flag(daily_periods, "continuous_flow_alarm"),
                _first_present(
                    usage_payload if isinstance(usage_payload, dict) else {},
                    "continuousFlowAlarm",
                    "continuous_flow_alarm",
                    "continuousFlowStatus",
                    "continuous_flow_status",
                ),
            ),
            "data_latest_update_status": latest_data_status,
            "latest_data_date": latest_period["end"] if latest_period else None,
            "latest_update_date": latest_update,
            "included_day_count": daily_summary.get("included_day_count"),
            "estimated_day_count": estimated_day_count,
            "missing_day_count": missing_day_count,
            "total_cost": _first_non_none(
                daily_summary.get("total_cost"),
                _find_first_key(usage_payload, "totalCost", "total_cost"),
            ),
            "clean_water_cost": _first_non_none(
                daily_summary.get("clean_water_cost"),
                _find_first_key(usage_payload, "cleanWaterCost", "clean_water_cost"),
            ),
            "sewerage_cost": _first_non_none(
                daily_summary.get("sewerage_cost"),
                _find_first_key(usage_payload, "sewerageCost", "sewerage_cost"),
            ),
            "meter_configured": bool(self.meter_reference),
            "account_configured": bool(self.account_reference),
            "last_successful_update": datetime.now().isoformat(timespec="seconds"),
            "status": "ok",
        }

    async def async_fetch_current_consumption(self) -> dict[str, Any]:
        """Fetch current meter reading or consumption.

        TODO: Implement once Yorkshire Water's current consumption endpoint is
        captured. Expected normalized return shape:
        {"meter_reading_m3": float | None, "estimated": bool, "reading_date": str | None}
        """
        if not YORKSHIRE_WATER_CURRENT_CONSUMPTION_PATH:
            return {
                "meter_reading_m3": None,
                "estimated": None,
                "reading_date": None,
            }

        payload = await self._async_request_json(
            "GET",
            YORKSHIRE_WATER_CURRENT_CONSUMPTION_PATH,
            endpoint_label="current_consumption",
        )
        _ensure_response_shape("current_consumption", payload, dict)
        return self._normalise_current_consumption(payload)

    async def async_fetch_daily_consumption(self) -> list[UsagePeriod]:
        """Fetch daily consumption periods.

        TODO: Update this request once the Yorkshire Water endpoint and query
        parameters are confirmed from a live portal capture.
        """
        if not YORKSHIRE_WATER_DAILY_CONSUMPTION_PATH:
            raise YorkshireWaterEndpointNotConfiguredError(
                "Yorkshire Water daily consumption endpoint is not configured yet"
            )

        payload = await self._async_request_json(
            "GET",
            YORKSHIRE_WATER_DAILY_CONSUMPTION_PATH,
            endpoint_label="your_usage",
        )
        _ensure_response_shape("your_usage", payload, dict)
        return self._normalise_daily_consumption(payload)

    async def async_fetch_monthly_consumption(self) -> list[UsagePeriod]:
        """Fetch monthly consumption periods for future estimated readings."""
        if not YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH:
            return []

        payload = await self._async_request_json(
            "GET",
            YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH,
            endpoint_label="monthly_usage",
        )
        _ensure_response_shape("monthly_usage", payload, (dict, list))
        return self._normalise_daily_consumption(payload)

    async def _async_request_json(
        self,
        method: str,
        path: str,
        *,
        endpoint_label: str,
        params: dict[str, Any] | None = None,
    ) -> JsonPayload:
        """Make a redacted authenticated request and return JSON."""
        if not YORKSHIRE_WATER_API_BASE_URL:
            raise YorkshireWaterEndpointNotConfiguredError(
                "Yorkshire Water API base URL is not configured yet"
            )
        if not self._session_token:
            raise YorkshireWaterEndpointNotConfiguredError(
                "Yorkshire Water bearer token is not configured yet"
            )

        url = f"{YORKSHIRE_WATER_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/json",
            # TODO: Wire this to a stored OAuth access token once token refresh
            # and response schemas are implemented. Do not add cookie handling
            # unless redacted response testing proves it is required.
            "Authorization": f"Bearer {self._session_token}",
        }
        request_params = {
            key: value for key, value in (params or {}).items() if value is not None
        }

        _LOGGER.debug("Yorkshire Water API request: %s %s", method, endpoint_label)

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=request_params,
                timeout=30,
            ) as response:
                await self._raise_for_status(response)
                status = response.status
                payload = await response.json(content_type=None)
        except ClientError as err:
            raise YorkshireWaterError(f"Error communicating with Yorkshire Water: {err}") from err

        if not isinstance(payload, (dict, list)):
            raise YorkshireWaterSchemaError(
                "Unexpected Yorkshire Water response shape for "
                f"{endpoint_label}: {_json_type_name(payload)}"
            )
        _LOGGER.debug(
            "Yorkshire Water API response: %s status=%s top_level=%s",
            endpoint_label,
            status,
            _json_type_name(payload),
        )
        return payload

    async def _raise_for_status(self, response: ClientResponse) -> None:
        """Map HTTP errors to structured integration errors."""
        if response.status < 400:
            return

        if response.status == 401:
            raise YorkshireWaterExpiredSessionError("Yorkshire Water session expired")
        if response.status == 403:
            raise YorkshireWaterAuthError("Yorkshire Water rejected the supplied credentials")
        if response.status == 404:
            raise YorkshireWaterMeterNotFoundError("Yorkshire Water account or meter was not found")
        if response.status == 429:
            raise YorkshireWaterRateLimitError("Yorkshire Water rate limit exceeded")
        if 500 <= response.status <= 599:
            raise YorkshireWaterUpstreamUnavailableError(
                f"Yorkshire Water upstream service returned HTTP {response.status}"
            )

        raise YorkshireWaterError(f"Yorkshire Water API returned HTTP {response.status}")

    def _normalise_daily_consumption(self, payload: dict[str, Any]) -> list[UsagePeriod]:
        """Normalize a captured daily consumption payload.

        Supports a few common response shapes while endpoint discovery is in
        progress. Tighten this once the real Yorkshire Water schema is known.
        """
        raw_items = (
            payload.get("dailyConsumption")
            or payload.get("daily_consumption")
            or payload.get("readings")
            or payload.get("items")
            or payload.get("data")
        )
        if not isinstance(raw_items, list):
            raise YorkshireWaterSchemaError("Daily consumption payload did not contain a list")

        periods: list[UsagePeriod] = []
        for item in raw_items:
            if not isinstance(item, dict):
                raise YorkshireWaterSchemaError("Daily consumption item was not an object")

            start_value = _first_present(item, "startDate", "start_date", "date")
            end_value = _first_present(item, "endDate", "end_date") or start_value
            value = _first_present(item, "value", "usage", "consumption")
            unit = _first_present(item, "unit", "uom", "unitOfMeasure")

            if start_value is None or value is None or unit is None:
                raise YorkshireWaterSchemaError(
                    "Daily consumption item missed date, value, or unit"
                )

            periods.append(
                UsagePeriod(
                    start=_parse_date(start_value),
                    end=_parse_date(end_value),
                    value=float(value),
                    unit=str(unit),
                    source=item.get("source"),
                    freshness=item.get("freshness") or item.get("lastUpdated"),
                )
            )

        if not periods:
            raise YorkshireWaterNoSmartMeterDataError(
                "Yorkshire Water returned no daily smart meter data"
            )
        return periods

    def _normalise_current_consumption(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize a current reading payload."""
        data = payload.get("currentConsumption") or payload.get("current") or payload
        if not isinstance(data, dict):
            raise YorkshireWaterSchemaError("Current consumption payload was not an object")

        value = _first_present(data, "meterReading", "meter_reading", "reading")
        unit = _first_present(data, "unit", "uom") or "m3"
        reading = None
        if value is not None:
            reading = UsagePeriod(
                start=date.today(),
                end=date.today(),
                value=float(value),
                unit=str(unit),
            ).cubic_metres

        return {
            "meter_reading_m3": round(reading, 3) if reading is not None else None,
            "estimated": data.get("estimated"),
            "reading_date": data.get("readingDate") or data.get("reading_date"),
        }

    @staticmethod
    def _period_as_dict(period: UsagePeriod) -> dict[str, Any]:
        """Serialize a usage period for sensor attributes."""
        return {
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
            "value_m3": round(period.cubic_metres, 3),
            "raw_value": period.value,
            "raw_unit": period.unit,
            "source": period.source,
            "freshness": period.freshness,
        }


def _parse_date(value: Any) -> date:
    """Parse date or datetime strings from API payloads."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        raise YorkshireWaterSchemaError(f"Unsupported date value: {value!r}")

    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _ensure_dict(data: Any, label: str) -> None:
    """Validate that a parser received a JSON object."""
    if not isinstance(data, dict):
        raise YorkshireWaterSchemaError(f"{label} was not a JSON object")


def _ensure_response_shape(
    endpoint_label: str,
    data: Any,
    expected: type | tuple[type, ...],
) -> None:
    """Validate a response shape without exposing payload content."""
    if not isinstance(data, expected):
        raise YorkshireWaterSchemaError(
            "Unexpected Yorkshire Water response shape for "
            f"{endpoint_label}: {_json_type_name(data)}"
        )


def _json_type_name(value: Any) -> str:
    """Return a simple JSON-ish type name for safe schema errors."""
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "list"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return "null"
    return type(value).__name__


def _parse_optional_datetime(value: Any) -> str | None:
    """Parse optional datetime strings, treating known sentinel dates as unset."""
    if value is None:
        return None
    if isinstance(value, str) and value.startswith("0001-01-01T00:00:00"):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise YorkshireWaterSchemaError(f"Unsupported datetime value: {value!r}")

    return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()


def _date_param(value: date | str) -> str:
    """Return a YYYY-MM-DD query parameter value."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        return _parse_date(value).isoformat()
    raise YorkshireWaterSchemaError(f"Unsupported date parameter: {type(value).__name__}")


def _normalise_optional_volume(value: Any, unit: Any) -> float | None:
    """Normalize an optional volume value to cubic metres."""
    if value is None:
        return None
    return UsagePeriod(
        start=date.today(),
        end=date.today(),
        value=float(value),
        unit=str(unit),
    ).cubic_metres


def _coerce_optional_float(value: Any) -> float | None:
    """Coerce an optional numeric value."""
    if value is None:
        return None
    return float(value)


def _extract_usage_periods(payload: JsonPayload, grain: str) -> list[dict[str, Any]]:
    """Extract usage periods from a captured usage payload."""
    if grain == "daily":
        if not isinstance(payload, dict):
            return []
        try:
            return [_period_from_normalized_dict(item) for item in parse_daily_consumption_response(payload)]
        except YorkshireWaterSchemaError:
            return []
    if grain == "monthly":
        return parse_monthly_consumption_response(payload)
    if grain == "yearly":
        if not isinstance(payload, dict):
            return []
        return parse_yearly_consumption_response(payload)
    raise YorkshireWaterSchemaError(f"Unsupported usage grain: {grain}")


def _period_from_normalized_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Convert an existing parser-normalized period to the summary shape."""
    start_value = item.get("start")
    end_value = item.get("end") or start_value
    value_m3 = item.get("value_m3")
    return {
        "start": start_value,
        "end": end_value,
        "start_date": _parse_date(start_value),
        "end_date": _parse_date(end_value),
        "value_litres": round(float(value_m3) * 1000, 2)
        if value_m3 is not None
        else None,
        "estimated": item.get("estimated"),
        "missing": item.get("missing"),
        "continuous_flow_alarm": item.get("continuous_flow_alarm"),
        "estimated_day_count": item.get("estimated_day_count"),
        "missing_day_count": item.get("missing_day_count"),
        "source": item.get("source"),
        "freshness": item.get("freshness"),
        "total_cost": _coerce_optional_float(item.get("total_cost")),
        "clean_water_cost": _coerce_optional_float(item.get("clean_water_cost")),
        "sewerage_cost": _coerce_optional_float(item.get("sewerage_cost")),
    }


def _period_from_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw usage period to litres."""
    start_value = _first_present(
        item,
        "startDate",
        "start_date",
        "fromDate",
        "from_date",
        "date",
        "periodStart",
    )
    end_value = (
        _first_present(
            item,
            "endDate",
            "end_date",
            "toDate",
            "to_date",
            "periodEnd",
        )
        or start_value
    )
    value = _first_present(
        item,
        "litres",
        "liters",
        "totalConsumptionLitres",
        "total_consumption_litres",
        "usageLitres",
        "usage_litres",
        "value",
        "usage",
        "consumption",
    )
    unit = _first_present(item, "unit", "uom", "unitOfMeasure") or (
        "litres"
        if _first_present(
            item,
            "litres",
            "liters",
            "totalConsumptionLitres",
            "total_consumption_litres",
            "usageLitres",
            "usage_litres",
        )
        is not None
        else "m3"
    )
    value_litres = _normalise_optional_litres(value, unit)
    return {
        "start": _parse_date(start_value).isoformat() if start_value else None,
        "end": _parse_date(end_value).isoformat() if end_value else None,
        "start_date": _parse_date(start_value) if start_value else date.min,
        "end_date": _parse_date(end_value) if end_value else date.min,
        "month": item.get("month"),
        "year": item.get("year"),
        "value_litres": round(value_litres, 2) if value_litres is not None else None,
        "estimated": _first_present(item, "estimated", "isEstimated", "is_estimated"),
        "estimated_day_count": _first_present(item, "estimatedDayCount", "estimated_day_count"),
        "missing_day_count": _first_present(item, "missingDayCount", "missing_day_count"),
        "source": item.get("source"),
        "freshness": item.get("freshness") or item.get("lastUpdated"),
        "total_cost": _coerce_optional_float(
            _first_present(
                item,
                "totalCostIncludingSewerage",
                "total_cost_including_sewerage",
                "totalCost",
                "total_cost",
            )
        ),
        "clean_water_cost": _coerce_optional_float(
            _first_present(
                item,
                "standardTariffCleanWaterCost",
                "standard_tariff_clean_water_cost",
                "cleanWaterCost",
                "clean_water_cost",
            )
        ),
        "sewerage_cost": _coerce_optional_float(
            _first_present(
                item,
                "standardTariffSewerageCost",
                "standard_tariff_sewerage_cost",
                "sewerageCost",
                "sewerage_cost",
            )
        ),
    }


def _normalise_optional_litres(value: Any, unit: Any) -> float | None:
    """Normalize an optional volume value to litres."""
    if value is None:
        return None
    normalised = str(unit).lower().replace("³", "3").replace(" ", "")
    numeric = float(value)
    if normalised in {"l", "litre", "litres", "liter", "liters"}:
        return numeric
    if normalised in {"m3", "cubicmetres", "cubicmeters"}:
        return numeric * 1000
    raise YorkshireWaterSchemaError(f"Unsupported water unit: {unit}")


def _total_from_periods(periods: list[dict[str, Any]]) -> float | None:
    """Total litre values from normalized periods."""
    values = [period["value_litres"] for period in periods if period["value_litres"] is not None]
    return round(sum(values), 2) if values else None


def _monthly_total_for_month(periods: list[dict[str, Any]], today: date) -> float | None:
    """Return the current month total from monthly summary periods only."""
    current_month = f"{today.month:02d}"
    for period in periods:
        if str(period.get("month") or "").zfill(2) == current_month:
            return period.get("value_litres")
    return None


def _count_missing_days(periods: list[dict[str, Any]]) -> int:
    """Count missing days between the first and latest daily usage period."""
    dated = sorted({period["start_date"] for period in periods if period["start_date"] != date.min})
    if len(dated) < 2:
        return 0
    expected_days = (dated[-1] - dated[0]).days + 1
    return max(expected_days - len(dated), 0)


def _sum_period_count(periods: list[dict[str, Any]], key: str) -> int:
    """Sum optional integer count fields from normalized periods."""
    total = 0
    for period in periods:
        value = period.get(key)
        if value is not None:
            total += int(value)
    return total


def _sum_period_field(periods: list[dict[str, Any]], key: str) -> float | None:
    """Sum optional numeric fields from normalized periods."""
    values = [
        float(period[key])
        for period in periods
        if period.get(key) is not None
    ]
    return round(sum(values), 2) if values else None


def _count_period_flag(periods: list[dict[str, Any]], key: str) -> int:
    """Count truthy boolean flags from normalized periods."""
    return sum(1 for period in periods if period.get(key) is True)


def _any_period_flag(periods: list[dict[str, Any]], key: str) -> bool | None:
    """Return True if any period has a truthy flag, False if any explicit false exists."""
    values = [period.get(key) for period in periods if period.get(key) is not None]
    if not values:
        return None
    return any(values)


def _usage_period_as_dict(period: dict[str, Any]) -> dict[str, Any]:
    """Serialize a normalized usage period for sensor attributes."""
    return {
        "start": period.get("start"),
        "end": period.get("end"),
        "month": period.get("month"),
        "year": period.get("year"),
        "value_litres": period.get("value_litres"),
        "estimated": period.get("estimated"),
        "missing": period.get("missing"),
        "continuous_flow_alarm": period.get("continuous_flow_alarm"),
        "estimated_day_count": period.get("estimated_day_count"),
        "missing_day_count": period.get("missing_day_count"),
        "source": period.get("source"),
        "freshness": period.get("freshness"),
        "total_cost": period.get("total_cost"),
        "clean_water_cost": period.get("clean_water_cost"),
        "sewerage_cost": period.get("sewerage_cost"),
    }


def _find_first_key(data: Any, *keys: str) -> Any:
    """Return the first matching key found in a nested JSON-like structure."""
    if isinstance(data, dict):
        for key in keys:
            if key in data:
                return data[key]
        for value in data.values():
            found = _find_first_key(value, *keys)
            if found is not None:
                return found
    if isinstance(data, list):
        for item in data:
            found = _find_first_key(item, *keys)
            if found is not None:
                return found
    return None


def _discovery_placeholder(
    *,
    route_name: str,
    method: str,
    endpoint_path: str,
    query_parameters: dict[str, str],
) -> dict[str, Any]:
    """Return non-live route metadata while response schemas are unknown."""
    return {
        "status": "schema_pending",
        "route_name": route_name,
        "method": method,
        "base_url": YORKSHIRE_WATER_SMART_METER_API_BASE_URL,
        "endpoint_path": endpoint_path,
        "query_parameters": query_parameters,
        "request_body_shape": None,
        "response_schema": None,
    }


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    """Return the first key present in a dict, preserving falsey values."""
    for key in keys:
        if key in data:
            return data[key]
    return None


def _first_non_none(*values: Any) -> Any:
    """Return the first value that is not None, preserving falsey values."""
    for value in values:
        if value is not None:
            return value
    return None

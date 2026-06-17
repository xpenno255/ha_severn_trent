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
    _ensure_dict(data, "Meter discovery payload")

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
    _ensure_dict(data, "Current consumption payload")

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
    }


def parse_daily_consumption_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a redacted daily consumption response into normalized periods."""
    _ensure_dict(data, "Daily consumption payload")

    # TODO: Replace these scaffold mappings once captured Yorkshire Water
    # schemas confirm daily usage field names, units, and completion markers.
    raw_items = (
        data.get("dailyConsumption")
        or data.get("daily_consumption")
        or data.get("items")
        or data.get("data")
    )
    if raw_items is None:
        return []
    if not isinstance(raw_items, list):
        raise YorkshireWaterSchemaError("Daily consumption payload did not contain a list")

    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise YorkshireWaterSchemaError("Daily consumption item was not an object")
        start_value = _first_present(item, "startDate", "start_date", "date")
        end_value = _first_present(item, "endDate", "end_date") or start_value
        value = _first_present(item, "value", "usage", "consumption")
        unit = _first_present(item, "unit", "uom", "unitOfMeasure") or "m3"
        volume = _normalise_optional_volume(value, unit)
        normalized.append(
            {
                "start": _parse_date(start_value).isoformat() if start_value else None,
                "end": _parse_date(end_value).isoformat() if end_value else None,
                "value_m3": round(volume, 3) if volume is not None else None,
                "source": item.get("source"),
                "freshness": item.get("freshness") or item.get("lastUpdated"),
            }
        )
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
        session_token: str,
        account_id: str | None = None,
        meter_id: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._session_token = session_token.strip()
        self.account_id = account_id.strip() if account_id else None
        self.meter_id = meter_id.strip() if meter_id else None

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
        """Return a discovery placeholder for the meter details endpoint."""
        _LOGGER.debug(
            "Yorkshire Water meter details route discovered: %s params=%s",
            YORKSHIRE_WATER_METER_DETAILS_ENDPOINT_PATH,
            self.redact({"accountReference": account_reference}),
        )
        return _discovery_placeholder(
            route_name="meter_details",
            method="GET",
            endpoint_path=YORKSHIRE_WATER_METER_DETAILS_ENDPOINT_PATH,
            query_parameters={"accountReference": _REDACTED},
        )

    async def async_get_current_consumption(self, meter_reference: str) -> dict[str, Any]:
        """Return a discovery placeholder for the current consumption endpoint."""
        _LOGGER.debug(
            "Yorkshire Water current consumption route discovered: %s params=%s",
            YORKSHIRE_WATER_CURRENT_CONSUMPTION_ENDPOINT_PATH,
            self.redact({"meterReference": meter_reference}),
        )
        return _discovery_placeholder(
            route_name="current_consumption",
            method="GET",
            endpoint_path=YORKSHIRE_WATER_CURRENT_CONSUMPTION_ENDPOINT_PATH,
            query_parameters={"meterReference": _REDACTED},
        )

    async def async_get_your_usage(self, meter_reference: str) -> dict[str, Any]:
        """Return a discovery placeholder for the your usage endpoint."""
        _LOGGER.debug(
            "Yorkshire Water your usage route discovered: %s params=%s",
            YORKSHIRE_WATER_YOUR_USAGE_ENDPOINT_PATH,
            self.redact({"meterReference": meter_reference}),
        )
        return _discovery_placeholder(
            route_name="your_usage",
            method="GET",
            endpoint_path=YORKSHIRE_WATER_YOUR_USAGE_ENDPOINT_PATH,
            query_parameters={"meterReference": _REDACTED},
        )

    async def async_fetch_usage_summary(self) -> dict[str, Any]:
        """Fetch and summarize current Yorkshire Water usage data."""
        daily_periods = await self.async_fetch_daily_consumption()
        current_reading = await self.async_fetch_current_consumption()

        today = date.today()
        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())
        previous_week_start = week_start - timedelta(days=7)
        previous_week_end = week_start - timedelta(days=1)

        by_start = {period.start: period for period in daily_periods}
        recent_periods = sorted(daily_periods, key=lambda item: item.start, reverse=True)
        last_seven = [
            period for period in daily_periods if today - timedelta(days=7) <= period.start < today
        ]

        def sum_range(start: date, end: date) -> float | None:
            values = [
                period.cubic_metres
                for period in daily_periods
                if start <= period.start <= end
            ]
            if not values:
                return None
            return round(sum(values), 3)

        yesterday_period = by_start.get(yesterday)
        today_period = by_start.get(today)

        return {
            "daily_periods": [self._period_as_dict(period) for period in recent_periods],
            "yesterday_usage_m3": round(yesterday_period.cubic_metres, 3)
            if yesterday_period
            else None,
            "yesterday_start": yesterday.isoformat(),
            "yesterday_end": yesterday.isoformat(),
            "today_usage_m3": round(today_period.cubic_metres, 3) if today_period else None,
            "today_start": today.isoformat(),
            "today_end": today.isoformat(),
            "daily_average_m3": round(
                sum(period.cubic_metres for period in last_seven) / len(last_seven),
                3,
            )
            if last_seven
            else None,
            "daily_average_period_start": (today - timedelta(days=7)).isoformat(),
            "daily_average_period_end": yesterday.isoformat(),
            "week_to_date_m3": sum_range(week_start, today),
            "week_start": week_start.isoformat(),
            "previous_week_m3": sum_range(previous_week_start, previous_week_end),
            "previous_week_start": previous_week_start.isoformat(),
            "previous_week_end": previous_week_end.isoformat(),
            "meter_reading_m3": current_reading.get("meter_reading_m3"),
            "meter_reading_estimated": current_reading.get("estimated"),
            "meter_reading_date": current_reading.get("reading_date"),
            "meter_id": self.meter_id,
            "account_id": self.account_id,
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
        )
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

        payload = await self._async_request_json("GET", YORKSHIRE_WATER_DAILY_CONSUMPTION_PATH)
        return self._normalise_daily_consumption(payload)

    async def async_fetch_monthly_consumption(self) -> list[UsagePeriod]:
        """Fetch monthly consumption periods for future estimated readings."""
        if not YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH:
            return []

        payload = await self._async_request_json("GET", YORKSHIRE_WATER_MONTHLY_CONSUMPTION_PATH)
        return self._normalise_daily_consumption(payload)

    async def _async_request_json(self, method: str, path: str) -> dict[str, Any]:
        """Make a redacted authenticated request and return JSON."""
        if not YORKSHIRE_WATER_API_BASE_URL:
            raise YorkshireWaterEndpointNotConfiguredError(
                "Yorkshire Water API base URL is not configured yet"
            )

        url = f"{YORKSHIRE_WATER_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/json",
            # TODO: Wire this to a stored OAuth access token once token refresh
            # and response schemas are implemented. Do not add cookie handling
            # unless redacted response testing proves it is required.
            "Authorization": f"Bearer {self._session_token}",
        }
        params = {
            "account_id": self.account_id,
            "meter_id": self.meter_id,
        }

        _LOGGER.debug(
            "Yorkshire Water API request: %s %s params=%s headers=%s",
            method,
            url,
            self.redact(params),
            self.redact(headers),
        )

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params={key: value for key, value in params.items() if value},
                timeout=30,
            ) as response:
                await self._raise_for_status(response)
                payload = await response.json(content_type=None)
        except ClientError as err:
            raise YorkshireWaterError(f"Error communicating with Yorkshire Water: {err}") from err

        _LOGGER.debug("Yorkshire Water API response: %s", self.redact(payload))
        if not isinstance(payload, dict):
            raise YorkshireWaterSchemaError("Yorkshire Water response was not a JSON object")
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

        text = await response.text()
        raise YorkshireWaterError(
            f"Yorkshire Water API returned HTTP {response.status}: {text[:120]}"
        )

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

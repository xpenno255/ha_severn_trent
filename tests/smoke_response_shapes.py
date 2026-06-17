"""Smoke checks for Yorkshire Water response shape handling."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, date, datetime
import importlib.util
import json
from pathlib import Path
import re
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def _load_api_module():
    """Load api.py without importing the Home Assistant package."""
    package = types.ModuleType("custom_components.yorkshire_water")
    package.__path__ = [str(ROOT / "custom_components/yorkshire_water")]
    sys.modules["custom_components.yorkshire_water"] = package

    for name in ("const", "api"):
        spec = importlib.util.spec_from_file_location(
            f"custom_components.yorkshire_water.{name}",
            ROOT / f"custom_components/yorkshire_water/{name}.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    return sys.modules["custom_components.yorkshire_water.api"]


class _Response:
    def __init__(self, payload, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def json(self, content_type=None):
        return self.payload


class _Session:
    def __init__(
        self,
        usage_fixture: str = "monthly_summary_list_response.json",
        daily_fixture: str = "daily_usage_object_response.json",
    ) -> None:
        self.usage_fixture = usage_fixture
        self.daily_fixture = daily_fixture

    def request(self, method, url, headers=None, params=None, timeout=None):
        if "meter-details" in url:
            return _Response(_fixture("meter_discovery_response.json"))
        if "current-consumption" in url:
            return _Response(_fixture("current_consumption_response.json"))
        if "daily-consumption" in url:
            assert params["meterReference"] == "METER-REDACTED"
            assert params["startDate"] == "2026-06-01"
            assert params["endDate"] == "2026-06-17"
            assert params["moveInDate"] in {"2026-06-01", "2099-06-25"}
            assert params["moveOutDate"] == "2026-06-17"
            assert params["timePeriod"] == 1
            return _Response(_fixture(self.daily_fixture))
        return _Response(_fixture(self.usage_fixture))


def _fixture(name: str):
    return json.loads((ROOT / "tests/fixtures/redacted_examples" / name).read_text())


def _fake_jwt(payload: dict) -> str:
    def encode(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode(payload)}.signature"


async def _main() -> None:
    api = _load_api_module()

    assert api.normalize_bearer_token("  'abc123'  ") == "abc123"
    assert api.normalize_bearer_token('Bearer "abc123"') == "abc123"

    token_json = json.dumps(
        {
            "id_token": _fake_jwt({"nonce": "REDACTED", "typ": "ID"}),
            "access_token": "ACCESS-TOKEN-REDACTED",
            "expires_in": 900,
            "token_type": "Bearer",
            "scope": "openid css-onlineaccount-api",
        }
    )
    fixed_now = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    auth_data = api.build_token_auth_data(
        token_response_json=token_json,
        now=fixed_now,
    )
    assert auth_data["access_token"] == "ACCESS-TOKEN-REDACTED"
    assert auth_data["token_expires_at"] == "2026-06-17T12:15:00+00:00"
    assert "id_token" not in auth_data
    assert auth_data["token_metadata"]["has_id_token"] is True

    expired_json = json.dumps(
        {
            "id_token": "TOKEN-REDACTED",
            "access_token": "TOKEN-REDACTED",
            "expires_in": -1,
            "token_type": "Bearer",
            "scope": "openid",
        }
    )
    try:
        api.build_token_auth_data(token_response_json=expired_json)
    except api.YorkshireWaterExpiredSessionError:
        pass
    else:
        raise AssertionError("Expected expired token response to be rejected")

    try:
        api.build_token_auth_data(
            raw_access_token=_fake_jwt({"nonce": "REDACTED", "typ": "ID"})
        )
    except api.YorkshireWaterAuthError:
        pass
    else:
        raise AssertionError("Expected ID token-looking input to be rejected")

    daily = api.parse_daily_consumption_response(_fixture("daily_usage_object_response.json"))
    assert daily[-1]["value_m3"] == 0.239
    daily_summary = api.parse_daily_consumption_summary(
        _fixture("daily_usage_object_response.json")
    )
    assert daily_summary["total_litres"] == 2438

    monthly = api.parse_monthly_consumption_response(
        _fixture("monthly_summary_list_response.json")
    )
    assert monthly[0]["value_litres"] == 2438
    assert monthly[0]["total_cost"] == 11.27

    yearly = api.parse_yearly_consumption_response(
        {"monthlyConsumption": _fixture("monthly_summary_list_response.json")}
    )
    assert yearly[0]["clean_water_cost"] == 5.08

    session = _Session()
    client = api.YorkshireWaterAPI(
        session,
        "TOKEN-REDACTED",
        account_reference="ACCOUNT-REDACTED",
    )
    summary = await client.async_fetch_usage_summary(today=date(2026, 6, 17))
    assert summary["yesterday_usage_litres"] == 239
    assert summary["today_usage_litres"] is None
    assert summary["today_status_detail"] == "latest_available_usage_data_is_2026-06-16"
    assert summary["week_to_date_litres"] == 455
    assert summary["previous_week_litres"] == 1373
    assert summary["daily_average_litres"] == 217.0
    assert summary["month_to_date_litres"] == 2438
    assert summary["year_to_date_litres"] is None
    assert summary["estimated_cumulative_usage_m3"] == 2.438
    assert summary["estimated_cumulative_total_litres"] == 2438
    assert summary["estimated_cumulative_source"] == "estimated_from_usage"
    assert summary["estimated_cumulative_energy_dashboard_compatible"] is True
    assert summary["data_latest_update_status"] is not None
    assert summary["yesterday_included_day_count"] == 1
    assert summary["today_included_day_count"] == 0
    assert summary["daily_average_included_day_count"] == 7
    assert summary["week_to_date_included_day_count"] == 2
    assert summary["previous_week_included_day_count"] == 7
    assert summary["month_to_date_included_day_count"] == 16
    assert summary["daily_average_periods"][0]["start"] == "2026-06-10"
    assert summary["daily_average_periods"][-1]["end"] == "2026-06-16"
    assert len(summary["daily_average_periods"]) == 7
    assert summary["estimated_day_count"] == 0
    assert summary["missing_day_count"] == 0
    assert summary["yesterday_clean_water_cost"] == 0.5
    assert summary["month_to_date_total_cost"] == 11.27
    assert summary["meter_reading_m3"] is None
    assert summary["meter_reading_status"] == "not_implemented"
    assert summary["status"] == "ok"

    yearly_client = api.YorkshireWaterAPI(
        _Session("yearly_usage_object_response.json"),
        "TOKEN-REDACTED",
        account_reference="ACCOUNT-REDACTED",
    )
    yearly_summary = await yearly_client.async_fetch_usage_summary(today=date(2026, 6, 17))
    assert yearly_summary["year_to_date_litres"] == 5432
    assert yearly_summary["year_to_date_included_day_count"] == 2
    assert yearly_summary["estimated_cumulative_usage_m3"] == 5.432

    session.usage_fixture = "monthly_summary_shrunk_response.json"
    shrunk_summary = await client.async_fetch_usage_summary(today=date(2026, 6, 17))
    assert shrunk_summary["estimated_cumulative_usage_m3"] == 2.438
    assert shrunk_summary["estimated_cumulative_total_litres"] == 2438
    assert shrunk_summary["estimated_cumulative_source_total_litres"] == 1000
    assert (
        shrunk_summary["estimated_cumulative_status_detail"]
        == "preserved_previous_value_source_total_decreased"
    )

    sensor_source = (ROOT / "custom_components/yorkshire_water/sensor.py").read_text()
    cumulative_block = _sensor_block(sensor_source, "estimated_cumulative_usage")
    assert "state_class=SensorStateClass.TOTAL_INCREASING" in cumulative_block
    for period_key in (
        "yesterday_usage",
        "today_usage",
        "daily_average",
        "week_to_date",
        "previous_week",
        "month_to_date",
        "year_to_date",
    ):
        assert "SensorStateClass.TOTAL_INCREASING" not in _sensor_block(
            sensor_source,
            period_key,
        )

    expired_client = api.YorkshireWaterAPI(
        _Session(),
        "TOKEN-REDACTED",
        account_reference="ACCOUNT-REDACTED",
        token_expires_at="2000-01-01T00:00:00+00:00",
    )
    try:
        await expired_client.async_fetch_usage_summary(today=date(2026, 6, 17))
    except api.YorkshireWaterExpiredSessionError:
        pass
    else:
        raise AssertionError("Expected expired API token to stop before requests")

    try:
        api.parse_daily_consumption_response(_fixture("monthly_summary_list_response.json"))
    except api.YorkshireWaterSchemaError as err:
        assert str(err) == "Unexpected Yorkshire Water response shape for your_usage: list"
    else:
        raise AssertionError("Expected daily parser to reject a list response")

    print("response shape smoke ok")


def _sensor_block(source: str, key: str) -> str:
    """Return one sensor description block from sensor.py source text."""
    match = re.search(
        rf'YorkshireWaterSensorEntityDescription\(\n\s+key="{key}".*?'
        r"\n\s+\),",
        source,
        re.DOTALL,
    )
    assert match is not None, f"Missing sensor block for {key}"
    return match.group(0)


if __name__ == "__main__":
    asyncio.run(_main())

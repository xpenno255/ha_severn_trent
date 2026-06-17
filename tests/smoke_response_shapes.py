"""Smoke checks for Yorkshire Water response shape handling."""

from __future__ import annotations

import asyncio
from datetime import date
import importlib.util
import json
from pathlib import Path
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
    def request(self, method, url, headers=None, params=None, timeout=None):
        if "meter-details" in url:
            return _Response(_fixture("meter_discovery_response.json"))
        if "current-consumption" in url:
            return _Response(_fixture("current_consumption_response.json"))
        if "daily-consumption" in url:
            assert params["meterReference"] == "METER-REDACTED"
            assert params["startDate"] == "2026-06-01"
            assert params["endDate"] == "2026-06-17"
            assert params["moveInDate"] == "2099-06-25"
            assert params["moveOutDate"] == "2026-06-17"
            assert params["timePeriod"] == 1
            return _Response(_fixture("daily_usage_object_response.json"))
        return _Response(_fixture("monthly_summary_list_response.json"))


def _fixture(name: str):
    return json.loads((ROOT / "tests/fixtures/redacted_examples" / name).read_text())


async def _main() -> None:
    api = _load_api_module()

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

    client = api.YorkshireWaterAPI(
        _Session(),
        "TOKEN-REDACTED",
        account_reference="ACCOUNT-REDACTED",
    )
    summary = await client.async_fetch_usage_summary(today=date(2026, 6, 17))
    assert summary["yesterday_usage_litres"] == 239
    assert summary["today_usage_litres"] is None
    assert summary["week_to_date_litres"] == 455
    assert summary["previous_week_litres"] == 1373
    assert summary["daily_average_litres"] == 217.0
    assert summary["month_to_date_litres"] == 2438
    assert summary["estimated_day_count"] == 0
    assert summary["missing_day_count"] == 0
    assert summary["status"] == "ok"

    try:
        api.parse_daily_consumption_response(_fixture("monthly_summary_list_response.json"))
    except api.YorkshireWaterSchemaError as err:
        assert str(err) == "Unexpected Yorkshire Water response shape for your_usage: list"
    else:
        raise AssertionError("Expected daily parser to reject a list response")

    print("response shape smoke ok")


if __name__ == "__main__":
    asyncio.run(_main())

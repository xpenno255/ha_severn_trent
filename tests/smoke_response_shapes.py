"""Smoke checks for Yorkshire Water response shape handling."""

from __future__ import annotations

import asyncio
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
        return _Response(_fixture("monthly_summary_list_response.json"))


def _fixture(name: str):
    return json.loads((ROOT / "tests/fixtures/redacted_examples" / name).read_text())


async def _main() -> None:
    api = _load_api_module()

    daily = api.parse_daily_consumption_response(_fixture("daily_usage_object_response.json"))
    assert daily[0]["value_m3"] == 0.123

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
    summary = await client.async_fetch_usage_summary()
    assert summary["month_to_date_litres"] == 2438
    assert summary["estimated_day_count"] == 0
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

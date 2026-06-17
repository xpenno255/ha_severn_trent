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
        token_payload=None,
    ) -> None:
        self.usage_fixture = usage_fixture
        self.daily_fixture = daily_fixture
        self.token_payload = token_payload or {
            "id_token": "TOKEN-REDACTED",
            "access_token": "ACCESS-TOKEN-REDACTED",
            "expires_in": 900,
            "token_type": "Bearer",
            "scope": "openid css-onlineaccount-api",
        }
        self.token_requests: list[dict] = []
        self.api_requests: list[str] = []

    def request(self, method, url, headers=None, params=None, data=None, timeout=None):
        if "connect/token" in url:
            assert method == "POST"
            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            self.token_requests.append(data)
            return _Response(self.token_payload)
        if "meter-details" in url:
            self.api_requests.append("meter_details")
            return _Response(_fixture("meter_discovery_response.json"))
        if "current-consumption" in url:
            self.api_requests.append("current_consumption")
            return _Response(_fixture("current_consumption_response.json"))
        if "daily-consumption" in url:
            self.api_requests.append("daily_consumption")
            assert params["meterReference"] == "METER-REDACTED"
            assert params["startDate"] == "2026-06-01"
            assert params["endDate"] == "2026-06-17"
            assert params["moveInDate"] in {"2026-06-01", "2099-06-25"}
            assert params["moveOutDate"] == "2026-06-17"
            assert params["timePeriod"] == 1
            return _Response(_fixture(self.daily_fixture))
        self.api_requests.append("your_usage")
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
    verifier = api.generate_pkce_code_verifier()
    challenge = api.generate_pkce_code_challenge(verifier)
    assert 43 <= len(verifier) <= 128
    assert len(challenge) == 43
    assert api.generate_oauth_state() != api.generate_oauth_state()
    auth_params = api.build_oauth_authorization_params(challenge, "STATE-REDACTED")
    assert auth_params["client_id"] == "css-onlineaccount-fe"
    assert auth_params["response_type"] == "code"
    assert auth_params["code_challenge"] == challenge
    assert auth_params["code_challenge_method"] == "S256"
    assert auth_params["state"] == "STATE-REDACTED"
    assert "css-onlineaccount-api" in auth_params["scope"]
    api.validate_oauth_state("STATE-REDACTED", "STATE-REDACTED")
    try:
        api.validate_oauth_state("STATE-REDACTED", "STATE-MISMATCH-REDACTED")
    except api.YorkshireWaterStateMismatchError:
        pass
    else:
        raise AssertionError("Expected mismatched OAuth state to be rejected")
    code, state = api.extract_authorization_code(
        "https://my.yorkshirewater.com/account/callback/response?"
        "code=AUTH-CODE-REDACTED&state=STATE-REDACTED"
    )
    assert code == "AUTH-CODE-REDACTED"
    assert state == "STATE-REDACTED"
    assert api.extract_authorization_code("AUTH-CODE-REDACTED") == (
        "AUTH-CODE-REDACTED",
        None,
    )
    exchange_body = api.build_token_exchange_body(
        "AUTH-CODE-REDACTED",
        "CODE-VERIFIER-REDACTED",
    )
    assert exchange_body == {
        "client_id": "css-onlineaccount-fe",
        "grant_type": "authorization_code",
        "redirect_uri": "https://my.yorkshirewater.com/account/callback/response",
        "code": "AUTH-CODE-REDACTED",
        "code_verifier": "CODE-VERIFIER-REDACTED",
    }
    assert api.build_refresh_token_body("TOKEN-REDACTED") == {
        "client_id": "css-onlineaccount-fe",
        "grant_type": "refresh_token",
        "refresh_token": "TOKEN-REDACTED",
    }
    redacted = api.YorkshireWaterAPI.redact(exchange_body)
    assert redacted["code"] == "<redacted>"
    assert redacted["code_verifier"] == "<redacted>"

    token_json = json.dumps(
        {
            "id_token": _fake_jwt({"nonce": "REDACTED", "typ": "ID"}),
            "access_token": "ACCESS-TOKEN-REDACTED",
            "refresh_token": "TOKEN-REDACTED",
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
    assert auth_data["refresh_token"] == "TOKEN-REDACTED"
    assert auth_data["token_expires_at"] == "2026-06-17T12:15:00+00:00"
    assert "id_token" not in auth_data
    assert auth_data["token_metadata"]["has_id_token"] is True
    assert auth_data["token_metadata"]["has_refresh_token"] is True

    no_refresh_auth_data = api.build_token_auth_data(
        token_response_json=json.dumps(
            {
                "id_token": "TOKEN-REDACTED",
                "access_token": "ACCESS-TOKEN-REDACTED",
                "expires_in": 900,
                "token_type": "Bearer",
                "scope": "openid",
            }
        ),
        now=fixed_now,
    )
    assert no_refresh_auth_data["refresh_token"] is None
    assert no_refresh_auth_data["token_metadata"]["has_refresh_token"] is False
    fresh_reauth_data = api.build_token_auth_data(
        token_response_json=json.dumps(
            {
                "id_token": "TOKEN-REDACTED",
                "access_token": "TOKEN-REDACTED",
                "expires_in": 900,
                "token_type": "Bearer",
                "scope": "openid",
            }
        ),
        now=fixed_now,
    )
    assert fresh_reauth_data["access_token"] == "TOKEN-REDACTED"
    assert fresh_reauth_data["token_expires_at"] == "2026-06-17T12:15:00+00:00"

    token_session = _Session()
    token_client = api.YorkshireWaterAPI(token_session, None)
    exchanged = await token_client.async_exchange_authorization_code(
        "AUTH-CODE-REDACTED",
        "CODE-VERIFIER-REDACTED",
        now=fixed_now,
    )
    assert exchanged["access_token"] == "ACCESS-TOKEN-REDACTED"
    assert token_session.token_requests[-1] == exchange_body

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
    assert isinstance(summary["yesterday_clean_water_cost"], float)
    assert summary["yesterday_sewerage_cost"] == 0.61
    assert isinstance(summary["yesterday_sewerage_cost"], float)
    assert summary["yesterday_total_cost"] == 1.11
    assert summary["today_total_cost"] is None
    assert summary["week_to_date_total_cost"] == 2.11
    assert summary["previous_week_total_cost"] == 6.35
    assert summary["month_to_date_total_cost"] == 11.27
    assert summary["year_to_date_total_cost"] is None
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
    assert yearly_summary["year_to_date_total_cost"] == 25.11
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
    status_block = _sensor_block(sensor_source, "status")
    assert '"token_status": data.get("token_status")' in status_block
    assert '"refresh_available": data.get("refresh_available")' in status_block
    for cost_key in (
        "yesterday_cost",
        "today_cost",
        "week_to_date_cost",
        "previous_week_cost",
        "month_to_date_cost",
        "year_to_date_cost",
    ):
        cost_block = _sensor_block(sensor_source, cost_key)
        assert "device_class=SensorDeviceClass.MONETARY" in cost_block
        assert "state_class=SensorStateClass.TOTAL" in cost_block
        assert 'native_unit_of_measurement="GBP"' in cost_block
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

    expired_session = _Session()
    expired_client = api.YorkshireWaterAPI(
        expired_session,
        "TOKEN-REDACTED",
        account_reference="ACCOUNT-REDACTED",
        token_expires_at="2000-01-01T00:00:00+00:00",
    )
    try:
        await expired_client.async_fetch_usage_summary(today=date(2026, 6, 17))
    except api.YorkshireWaterRefreshUnavailableError as err:
        assert "TOKEN-REDACTED" not in str(err)
        assert "TOKEN-REDACTED" not in str(err)
    else:
        raise AssertionError("Expected expired API token to stop before requests")
    assert expired_session.api_requests == []
    expired_status = api.build_expired_token_status_data(
        account_configured=True,
        meter_configured=False,
        last_successful_update="2026-06-17T12:00:00",
        latest_data_date="2026-06-16",
        latest_update_date="2026-06-17T00:00:00+00:00",
    )
    assert expired_status == {
        "status": "reauth_required",
        "status_detail": "access_token_expired_reauth_required",
        "token_status": "token_expired",
        "refresh_available": False,
        "account_configured": True,
        "meter_configured": False,
        "latest_data_date": "2026-06-16",
        "latest_update_date": "2026-06-17T00:00:00+00:00",
        "last_successful_update": "2026-06-17T12:00:00",
    }
    assert "TOKEN-REDACTED" not in json.dumps(expired_status)

    refresh_session = _Session(
        token_payload={
            "id_token": "TOKEN-REDACTED",
            "access_token": "ACCESS-TOKEN-REDACTED",
            "expires_in": 900,
            "token_type": "Bearer",
            "scope": "openid css-onlineaccount-api",
        }
    )
    refresh_client = api.YorkshireWaterAPI(
        refresh_session,
        "TOKEN-REDACTED",
        account_reference="ACCOUNT-REDACTED",
        token_expires_at="2000-01-01T00:00:00+00:00",
        refresh_token="TOKEN-REDACTED",
    )
    refreshed_summary = await refresh_client.async_fetch_usage_summary(
        today=date(2026, 6, 17)
    )
    assert refreshed_summary["status"] == "ok"
    assert refresh_session.token_requests[0] == {
        "client_id": "css-onlineaccount-fe",
        "grant_type": "refresh_token",
        "refresh_token": "TOKEN-REDACTED",
    }
    pending_auth = refresh_client.consume_pending_auth_update()
    assert pending_auth["access_token"] == "ACCESS-TOKEN-REDACTED"
    assert pending_auth["refresh_token"] == "TOKEN-REDACTED"

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

"""Behaviour regressions found in the September 2026 integration review."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorStateClass

from custom_components.severn_trent.api import (
    REQUEST_TIMEOUT, WATER_TIME_ZONE, _api_dt, _water_volume,
)
from custom_components.severn_trent.sensor import (
    SevernTrentYesterdayUsageSensor, SevernTrentWeekToDateSensor,
    SevernTrentPreviousWeekSensor, SevernTrentEstimatedMeterReadingSensor,
)
from .conftest import _make_response, AUTH_SUCCESS_RESPONSE


class FrozenDateTime(datetime):
    current = datetime(2026, 9, 13, 12, tzinfo=WATER_TIME_ZONE)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)


def readings_response(days):
    return {"data": {"account": {"properties": [{"measurements": {"edges": [
        {"node": {"startAt": f"{day}T00:00:00+01:00", "value": value, "unit": "m³"}}
        for day, value in days.items()
    ]}}]}}}


def fetch_usage(api, days, now=None):
    response = _make_response(readings_response(days))
    empty = _make_response(readings_response({}))
    with (
        patch.object(api, "authenticate", return_value=True),
        patch.object(api.session, "post", side_effect=[response, empty]),
        patch("custom_components.severn_trent.api.datetime", FrozenDateTime),
        patch.object(FrozenDateTime, "current", now or FrozenDateTime.current),
    ):
        return api.get_meter_readings()


def complete_days():
    # Previous Monday through Saturday: older days deliberately differ.
    return {f"2026-09-{day:02}": 1 if day >= 6 else 10 for day in range(1, 13)} | {"2026-08-31": 10}


def test_average_uses_exactly_last_seven_days(authenticated_api):
    result = fetch_usage(authenticated_api, complete_days())
    assert result["daily_average"] == 1
    assert result["total_7day_usage"] == 7
    assert result["week_to_date_usage"] == 6
    assert result["previous_week_usage"] == 61
    assert len(result["recent_readings"]) == 7


def test_missing_yesterday_is_unknown_not_zero(authenticated_api):
    days = complete_days()
    del days["2026-09-12"]
    result = fetch_usage(authenticated_api, days)
    assert result["yesterday_usage"] is None
    assert result["daily_average"] is None
    assert result["week_to_date_usage"] is None
    assert result["previous_week_usage"] == 61
    assert result["days_in_average"] == 6


def test_actual_zero_is_preserved(authenticated_api):
    days = complete_days()
    days["2026-09-12"] = 0
    result = fetch_usage(authenticated_api, days)
    assert result["yesterday_usage"] == 0
    assert result["daily_average"] == pytest.approx(6 / 7, abs=0.001)


def test_monday_reset_uses_british_calendar(authenticated_api):
    now = datetime(2026, 9, 14, 0, 30, tzinfo=WATER_TIME_ZONE)
    days = {f"2026-09-{d:02}": 1 for d in range(7, 14)}
    result = fetch_usage(authenticated_api, days, now)
    assert result["week_start_date"] == "2026-09-14"
    assert result["week_to_date_usage"] == 0
    assert result["previous_week_usage"] == 7
    assert result["yesterday_date"] == "2026-09-13"


def test_missing_previous_week_day_is_not_partial_total(authenticated_api):
    days = complete_days()
    del days["2026-09-01"]
    result = fetch_usage(authenticated_api, days)
    assert result["previous_week_usage"] is None
    assert result["daily_average"] == 1


@pytest.mark.parametrize("value", [None, "bad", "NaN", "Infinity", -1])
def test_invalid_reading_does_not_become_zero(authenticated_api, value):
    days = complete_days()
    days["2026-09-12"] = value
    result = fetch_usage(authenticated_api, days)
    assert result["yesterday_usage"] is None
    assert result["daily_average"] is None


@pytest.mark.parametrize("month,offset", [(1, 0), (7, 1)])
def test_api_datetime_converts_bst_to_utc(month, offset):
    dt = datetime(2026, month, 15, 12, tzinfo=WATER_TIME_ZONE)
    assert _api_dt(dt) == f"2026-{month:02}-15T{12-offset:02}:00:00Z"


@pytest.mark.parametrize("day,hours", [("2026-03-29", 23), ("2026-10-25", 25)])
def test_dst_days_have_correct_interval_length(day, hours):
    start = datetime.fromisoformat(day).replace(tzinfo=WATER_TIME_ZONE)
    finish = start + timedelta(days=1)
    assert (datetime.fromisoformat(_api_dt(finish)) - datetime.fromisoformat(_api_dt(start))).total_seconds() == hours * 3600


def test_litres_are_converted_to_cubic_metres():
    assert _water_volume({"value": "250", "unit": "L"}) == 0.25
    with pytest.raises(ValueError):
        _water_volume({"value": "250", "unit": "kWh"})


def sensor_instance(sensor_type, smart):
    coordinator = SimpleNamespace(data={"smart_meter": smart}, last_update_success=True,
                                  async_request_refresh=AsyncMock())
    sensor = sensor_type(coordinator, "test-account")
    sensor.async_write_ha_state = MagicMock()
    sensor._handle_coordinator_update()
    return sensor, coordinator


@pytest.mark.parametrize("sensor_type,value_key,date_key", [
    (SevernTrentYesterdayUsageSensor, "yesterday_usage", "yesterday_date"),
    (SevernTrentWeekToDateSensor, "week_to_date_usage", "week_start_date"),
    (SevernTrentPreviousWeekSensor, "previous_week_usage", "previous_week_start_date"),
])
def test_period_totals_have_explicit_reset(sensor_type, value_key, date_key):
    sensor, coordinator = sensor_instance(sensor_type, {value_key: 2, date_key: "2026-09-07"})
    assert sensor.state_class == SensorStateClass.TOTAL
    first_reset = sensor.last_reset
    assert first_reset.utcoffset() == timedelta(hours=1)
    # Downward correction within one period must not be a new cycle.
    coordinator.data["smart_meter"][value_key] = 1.8
    sensor._handle_coordinator_update()
    assert sensor.last_reset == first_reset
    # Even equal totals in different periods must start a new cycle.
    coordinator.data["smart_meter"][date_key] = "2026-09-14"
    sensor._handle_coordinator_update()
    assert sensor.last_reset > first_reset
    assert sensor.native_value == 1.8
    # Failed fetches must not advance the reset clock.
    coordinator.data["smart_meter"] = {value_key: None, date_key: "2026-09-21"}
    last_reset = sensor.last_reset
    sensor._handle_coordinator_update()
    assert not sensor.available
    assert sensor.last_reset == last_reset


def test_week_to_date_zero_on_monday_is_available():
    sensor, _ = sensor_instance(SevernTrentWeekToDateSensor, {
        "week_to_date_usage": 0, "week_start_date": "2026-09-14",
    })
    assert sensor.available
    assert sensor.native_value == 0


@pytest.mark.asyncio
async def test_manual_entity_refresh_uses_shared_coordinator():
    sensor, coordinator = sensor_instance(SevernTrentWeekToDateSensor, {})
    assert not sensor.should_poll
    await sensor.async_update()
    coordinator.async_request_refresh.assert_awaited_once()


def test_zero_official_reading_is_valid():
    sensor, coordinator = sensor_instance(SevernTrentEstimatedMeterReadingSensor, {
        "monthly_readings": [{"start_date": "2026-09-01", "value": 0}],
    })
    coordinator.data["manual_meter"] = {"latest_reading": 0, "reading_date": "2026-09-01"}
    with patch("custom_components.severn_trent.sensor.datetime", FrozenDateTime):
        sensor._handle_coordinator_update()
    assert sensor.native_value == 0
    assert sensor.state_class == SensorStateClass.TOTAL


def test_authentication_does_not_log_tokens(authenticated_api, caplog):
    caplog.set_level("DEBUG")
    with patch.object(authenticated_api.session, "post", return_value=_make_response(AUTH_SUCCESS_RESPONSE)) as post:
        assert authenticated_api.authenticate()
    token_data = AUTH_SUCCESS_RESPONSE["data"]["obtainKrakenToken"]
    assert token_data["token"] not in caplog.text
    assert token_data["refreshToken"] not in caplog.text
    assert post.call_args.kwargs["timeout"] == REQUEST_TIMEOUT


def test_monthly_http_failure_keeps_daily_totals(authenticated_api):
    import requests
    with (
        patch.object(authenticated_api, "authenticate", return_value=True),
        patch.object(authenticated_api.session, "post", side_effect=[
            _make_response(readings_response(complete_days())), requests.Timeout(),
        ]),
        patch("custom_components.severn_trent.api.datetime", FrozenDateTime),
    ):
        result = authenticated_api.get_meter_readings()
    assert result["daily_average"] == 1
    assert result["monthly_readings"] == []


def test_estimate_requires_complete_history():
    sensor, coordinator = sensor_instance(SevernTrentEstimatedMeterReadingSensor, {
        "monthly_readings": [{"start_date": "2026-09-01", "value": 3}],
    })
    coordinator.data["manual_meter"] = {"latest_reading": 100, "reading_date": "2026-08-01"}
    with patch("custom_components.severn_trent.sensor.datetime", FrozenDateTime):
        sensor._handle_coordinator_update()
    assert sensor.native_value is None
    assert sensor.extra_state_attributes["missing_periods"] == ["2026-08-01"]


def test_estimate_uses_partial_month_once_and_ignores_extra_days():
    sensor, coordinator = sensor_instance(SevernTrentEstimatedMeterReadingSensor, {
        "monthly_readings": [
            {"start_date": "2026-08-01", "value": 999},
            {"start_date": "2026-09-01", "value": 3},
        ],
        "daily_readings_since_official": [
            {"date": "2026-08-30", "value": 999},
            {"date": "2026-08-31", "value": 0.5},
            {"date": "2026-09-01", "value": 999},
        ],
    })
    coordinator.data["manual_meter"] = {"latest_reading": 100, "reading_date": "2026-08-31"}
    with patch("custom_components.severn_trent.sensor.datetime", FrozenDateTime):
        sensor._handle_coordinator_update()
    assert sensor.native_value == 103.5
    assert sensor.extra_state_attributes["daily_periods_included"] == 1
    assert sensor.extra_state_attributes["monthly_periods_included"] == 1


def test_midmonth_baseline_does_not_silently_lose_missing_daily_usage():
    sensor, coordinator = sensor_instance(SevernTrentEstimatedMeterReadingSensor, {
        "monthly_readings": [{"start_date": "2026-09-01", "value": 3}],
        "daily_readings_since_official": [],
    })
    coordinator.data["manual_meter"] = {"latest_reading": 100, "reading_date": "2026-08-31"}
    with patch("custom_components.severn_trent.sensor.datetime", FrozenDateTime):
        sensor._handle_coordinator_update()
    assert sensor.native_value is None
    assert sensor.extra_state_attributes["missing_periods"] == ["2026-08-31"]


def test_utc_daily_boundary_is_assigned_to_the_correct_bst_day(authenticated_api):
    payload = readings_response(complete_days())
    for edge in payload["data"]["account"]["properties"][0]["measurements"]["edges"]:
        edge["node"]["startAt"] = _api_dt(datetime.fromisoformat(edge["node"]["startAt"]))
    with (
        patch.object(authenticated_api, "authenticate", return_value=True),
        patch.object(authenticated_api.session, "post", side_effect=[
            _make_response(payload), _make_response(readings_response({})),
        ]) as post,
        patch("custom_components.severn_trent.api.datetime", FrozenDateTime),
    ):
        result = authenticated_api.get_meter_readings()
    assert result["daily_average"] == 1
    assert result["yesterday_usage"] == 1
    variables = post.call_args_list[0].kwargs["json"]["variables"]
    assert variables["endAt"] == "2026-09-12T23:00:00Z"


@pytest.mark.parametrize("sensor_type,value_key,date_key,old_value,new_value,expected_growth", [
    (SevernTrentWeekToDateSensor, "week_to_date_usage", "week_start_date", 2.5, 0, 0),
    (SevernTrentWeekToDateSensor, "week_to_date_usage", "week_start_date", 2.5, 0.4, 0.4),
    (SevernTrentYesterdayUsageSensor, "yesterday_usage", "yesterday_date", 0.4, 0.4, 0.4),
    (SevernTrentPreviousWeekSensor, "previous_week_usage", "previous_week_start_date", 3, 2, 2),
])
def test_home_assistant_recorder_counts_new_periods_without_negative_reset(
    sensor_type, value_key, date_key, old_value, new_value, expected_growth,
):
    """Exercise HA's actual statistics compiler; mock only persistence reads."""
    from homeassistant.components.sensor import recorder
    from homeassistant.core import State

    sensor, coordinator = sensor_instance(sensor_type, {value_key: old_value, date_key: "2026-09-07"})
    entity_id = "sensor.severn_trent_test"
    old_reset = sensor.last_reset
    coordinator.data["smart_meter"] = {value_key: new_value, date_key: "2026-09-14"}
    sensor._handle_coordinator_update()
    start = datetime(2026, 9, 14, tzinfo=timezone.utc)
    state = State(entity_id, str(sensor.native_value), {
        "state_class": sensor.state_class, "unit_of_measurement": "m³",
        "device_class": "water", "last_reset": sensor.last_reset.isoformat(),
    }, last_updated=start)
    with (
        patch.object(recorder, "_get_sensor_states", return_value=[state]),
        patch.object(recorder.history, "get_full_significant_states_with_session", return_value={entity_id: [state]}),
        patch.object(recorder, "get_instance", return_value=MagicMock()),
        patch.object(recorder.statistics, "get_metadata_with_session", return_value={}),
        patch.object(recorder.statistics, "get_latest_short_term_statistics_with_session", return_value={
            entity_id: [{"last_reset": old_reset.timestamp(), "state": old_value, "sum": 10}],
        }),
    ):
        result = recorder.compile_statistics(MagicMock(), MagicMock(), start, start + timedelta(minutes=5), {})
    assert result.platform_stats[0]["stat"]["sum"] == pytest.approx(10 + expected_growth)


def test_api_close_does_not_create_session(api):
    with patch("custom_components.severn_trent.api.requests.Session") as factory:
        api.close()
        factory.assert_not_called()
    session = api.session
    with patch.object(session, "close") as close:
        api.close()
        close.assert_called_once()
    assert api._session is None


def test_api_key_generation_closes_temporary_session():
    from custom_components.severn_trent.api import SevernTrentAPI
    with patch("custom_components.severn_trent.api.requests.Session") as factory:
        factory.return_value.post.return_value = _make_response({"data": {"regenerateSecretKey": {"key": "test"}}})
        assert SevernTrentAPI.generate_api_key("test-browser-token") == "test"
        factory.return_value.close.assert_called_once()


@pytest.mark.parametrize("yesterday,average,status", [(None, None, "stale_data"), (1, None, "incomplete_data"), (1, 1, "ok")])
def test_smart_status_explains_missing_data(yesterday, average, status):
    from custom_components.severn_trent.sensor import SevernTrentSmartMeterStatusSensor
    sensor, _ = sensor_instance(SevernTrentSmartMeterStatusSensor, {
        "all_readings": [{"date": "2026-09-12", "value": 1}],
        "yesterday_usage": yesterday, "daily_average": average,
        "week_to_date_usage": 1, "previous_week_usage": 1,
        "latest_daily_date": "2026-09-12",
    })
    assert sensor.native_value == status
    assert sensor.extra_state_attributes["latest_daily_date"] == "2026-09-12"

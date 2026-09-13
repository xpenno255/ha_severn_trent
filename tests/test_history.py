"""Historical attribution, correction replay, persistence and stale-data safeguards."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import requests
from homeassistant.components.recorder.statistics import async_add_external_statistics
from custom_components.severn_trent.api import APIError, AuthenticationError
from custom_components.severn_trent.statistics import build_statistics, WaterStatistics, usage_pattern
from tests.conftest import _make_response


@pytest.mark.parametrize('day,hours', [('2026-03-29',23),('2026-10-25',25),('2026-09-13',24)])
def test_statistics_use_original_day_through_dst(day,hours):
    rows = build_statistics({day:0.341})
    assert rows[-1]['sum'] - rows[0]['sum'] == 0.341
    assert (rows[-1]['start'] - rows[1]['start']).total_seconds()/3600 == hours-1
    assert all(row['start'].tzinfo == timezone.utc for row in rows)
    # Pass the actual HA import validator, mocking only its recorder queue.
    with patch('homeassistant.components.recorder.statistics.get_instance') as recorder:
        from homeassistant.components.recorder.models import StatisticMeanType
        async_add_external_statistics(MagicMock(),{
            'statistic_id':'severn_trent:water_test','source':'severn_trent',
            'name':'Water','unit_of_measurement':'m³','unit_class':'volume',
            'has_sum':True,'mean_type':StatisticMeanType.NONE},rows)
        recorder.return_value.async_import_statistics.assert_called_once()


def test_correction_and_earlier_backfill_recompute_all_later_sums():
    original = build_statistics({'2026-09-11':1,'2026-09-12':2})
    corrected = build_statistics({'2026-09-10':3,'2026-09-11':0.5,'2026-09-12':2})
    assert original[-1]['sum'] == 3
    assert corrected[-1]['sum'] == 5.5
    assert corrected[-1]['sum'] - corrected[-2]['sum'] == 2
    assert len({r['start'] for r in corrected}) == len(corrected)
    assert build_statistics({}) == []


def test_missing_days_are_not_fabricated():
    rows=build_statistics({'2026-09-10':0,'2026-09-12':2})
    from custom_components.severn_trent.api import WATER_TIME_ZONE
    assert not any(r['start'].astimezone(WATER_TIME_ZONE).date()==date(2026,9,11) for r in rows)
    assert rows[-1]['sum']==2


@pytest.mark.asyncio
async def test_history_idempotence_restart_and_failed_window():
    hass=MagicMock();hass.config.components={'recorder'}
    async def executor(f,*args):return f(*args)
    hass.async_add_executor_job=executor
    api=MagicMock();api.device_id='meter';api.market_supply_point_id='supply'
    api.get_daily_history.return_value={'2026-09-10':0.1}
    entry=SimpleNamespace(data={'account_number':'account'})
    store=MagicMock();store.async_load=AsyncMock(return_value=None);store.async_save=AsyncMock()
    with patch('custom_components.severn_trent.statistics.Store',return_value=store),patch('custom_components.severn_trent.statistics.async_add_external_statistics') as importer:
        history=WaterStatistics(hass,entry,api)
        await history.async_update(); assert importer.call_count==1
        await history.async_update(); assert importer.call_count==1
        api.get_daily_history.return_value={'2026-09-10':0.2}
        await history.async_update(); assert importer.call_count==2
        assert importer.call_args.args[2][-1]['sum']==0.2
        saved=dict(history.cache)
        api.get_daily_history.side_effect=APIError('temporary')
        await history.async_update(); assert history.cache==saved
        assert history.status['status']=='retrying'
        api.get_daily_history.side_effect=None
        store.async_load.return_value=saved
        restart=WaterStatistics(hass,entry,api)
        await restart.async_update(); assert importer.call_count==3
        assert restart.statistic_id==history.statistic_id
        api.device_id='replacement'
        assert WaterStatistics(hass,entry,api).statistic_id!=history.statistic_id


def test_high_usage_requires_complete_recent_baseline():
    today=date(2026,9,13)
    days={(today-timedelta(days=n)).isoformat():0.2 for n in range(1,32)}
    assert usage_pattern(days,today)['status']=='normal'
    for n in range(1,4):days[(today-timedelta(days=n)).isoformat()]=0.8
    assert usage_pattern(days,today)['status']=='elevated'
    del days['2026-09-12']
    assert usage_pattern(days,today)['status']=='insufficient_data'


@pytest.mark.parametrize('status,error',[(401,AuthenticationError),(403,AuthenticationError),(429,APIError),(500,APIError)])
def test_transport_classifies_real_http_failures(authenticated_api,status,error):
    response=_make_response({},status)
    response.raise_for_status.side_effect=requests.HTTPError('HTTP failure')
    with patch.object(authenticated_api.session,'post',return_value=response):
        with pytest.raises(error):authenticated_api.get_balance()
    if error is AuthenticationError:assert authenticated_api.token is None


def test_failed_refresh_clears_token_and_distinguishes_network(authenticated_api):
    with patch.object(authenticated_api.session,'post',side_effect=requests.Timeout()):
        assert not authenticated_api.authenticate()
    assert authenticated_api.token is None
    assert isinstance(authenticated_api.auth_error,APIError)


def test_daily_history_truncation_and_units(authenticated_api):
    prop={'measurements':{'pageInfo':{'hasNextPage':False},'edges':[{'node':{
        'value':'341','unit':'L','startAt':'2026-09-12T00:00:00+01:00','endAt':'2026-09-13T00:00:00+01:00'}}]}}
    with patch.object(authenticated_api.session,'post',return_value=_make_response({'data':{'account':{'properties':[prop]}}})):
        assert authenticated_api.get_daily_history('2026-09-12','2026-09-13')=={'2026-09-12':0.341}
        prop['measurements']['pageInfo']['hasNextPage']=True
        with pytest.raises(APIError,match='truncated'):authenticated_api.get_daily_history('2026-09-12','2026-09-13')


def test_meter_selection_searches_all_properties(authenticated_api):
    props=[{'activeWaterMeters':[{'serialNumber':'other'}]},{'activeWaterMeters':[{'serialNumber':'DEV456'}]}]
    assert authenticated_api._select_meter(props)['serialNumber']=='DEV456'
    authenticated_api.device_id='missing'
    assert authenticated_api._select_meter(props) is None


@pytest.mark.asyncio
async def test_diagnostics_exclude_identifiers_credentials_and_amounts():
    from custom_components.severn_trent.diagnostics import async_get_config_entry_diagnostics
    import json
    coordinator=SimpleNamespace(last_update_success=True,data={
        'smart_meter':{'latest_daily_date':'2026-09-12','meter_id':'secret-meter','daily_average':123.45},
        'meter_info':{'capability_type':'AMI','device_id':'secret-device'},
        'balance':{'balance_gbp':987.65},
        'history':{'status':'ready','statistic_id':'private-stat-id','days_imported':35}})
    hass=SimpleNamespace(data={'severn_trent':{'entry':{'coordinator':coordinator}}})
    result=await async_get_config_entry_diagnostics(hass,SimpleNamespace(entry_id='entry',data={'api_key':'secret-key'}))
    serialized=json.dumps(result)
    for secret in ['secret-meter','secret-device','secret-key','private-stat-id','987.65','123.45']:
        assert secret not in serialized
    assert result['daily_data']['latest_daily_date']=='2026-09-12'

"""Credential reuse and reauthentication must preserve account identity."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock,AsyncMock,patch
import pytest
from custom_components.severn_trent.config_flow import SevernTrentConfigFlow
from custom_components.severn_trent.api import APIError


def flow_fixture():
    flow=SevernTrentConfigFlow();flow.hass=MagicMock()
    async def executor(fn,*args):return fn(*args)
    flow.hass.async_add_executor_job=executor
    flow.hass.config_entries.async_reload=AsyncMock()
    flow.async_show_form=MagicMock(side_effect=lambda **kw:kw)
    flow.async_abort=MagicMock(side_effect=lambda **kw:kw)
    return flow


@pytest.mark.asyncio
async def test_reauth_wrong_account_does_not_replace_credentials():
    flow=flow_fixture()
    flow._reauth_entry=SimpleNamespace(data={'account_number':'original','api_key':'old'})
    async def connect(_):flow.account_numbers=['different'];flow.api_key='new'
    flow._connect=connect
    result=await flow.async_step_reauth_confirm({'api_key':'new'})
    assert result['errors']=={'base':'wrong_account'}
    flow.hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_reauth_updates_only_verified_siblings_sharing_old_key():
    flow=flow_fixture()
    entries=[SimpleNamespace(entry_id=str(i),data={'account_number':account,'api_key':key}) for i,(account,key) in enumerate([('one','old'),('two','old'),('three','other'),('unverified','old')])]
    flow._reauth_entry=entries[0];flow._async_current_entries=lambda:entries
    async def connect(_):flow.account_numbers=['one','two','three'];flow.api_key='new'
    flow._connect=connect
    result=await flow.async_step_reauth_confirm({'api_key':'new'})
    assert result=={'reason':'reauth_successful'}
    calls=flow.hass.config_entries.async_update_entry.call_args_list
    assert [c.args[0].entry_id for c in calls]==['0','1']
    assert all(c.kwargs['data']['api_key']=='new' for c in calls)
    assert flow.hass.config_entries.async_reload.await_count==2


@pytest.mark.asyncio
async def test_existing_key_reused_without_regeneration():
    flow=flow_fixture()
    flow.hass.config_entries.async_get_entry.return_value=SimpleNamespace(domain='severn_trent',data={'api_key':'existing'})
    api=MagicMock();api.authenticate.return_value=True;api.fetch_account_numbers.return_value=['one','two']
    with patch('custom_components.severn_trent.config_flow.SevernTrentAPI',return_value=api) as factory:
        await flow._connect({'existing_account':'entry'})
        factory.generate_api_key.assert_not_called()
        factory.assert_called_once_with(api_key='existing')


@pytest.mark.asyncio
async def test_network_failure_is_retryable_and_closes_client():
    flow=flow_fixture()
    api=MagicMock();api.authenticate.return_value=False;api.auth_error=APIError('temporary')
    with patch('custom_components.severn_trent.config_flow.SevernTrentAPI',return_value=api):
        result=await flow.async_step_user({'api_key':'existing'})
    assert result['errors']=={'base':'cannot_connect'}
    api.close.assert_called_once()

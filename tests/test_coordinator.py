"""Coordinator success/failure propagation without a running HA instance."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.severn_trent import async_setup_entry, async_unload_entry


@pytest.mark.parametrize("balance,should_fail", [({}, True), ({"balance_gbp": 0}, False)])
@pytest.mark.asyncio
async def test_empty_account_data_fails_but_financial_only_account_works(balance, should_fail):
    api = MagicMock()
    api.authenticate.return_value = True
    for name in ("get_manual_meter_readings", "get_rate_limit_info", "get_current_active_payment_schedule",
                 "get_meter_details", "get_outstanding_payment", "get_next_payment_forecast", "get_meter_readings"):
        getattr(api, name).return_value = {}
    api.get_balance.return_value = balance
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    async def executor(method, *args):
        return method(*args)
    hass.async_add_executor_job = executor
    entry = SimpleNamespace(entry_id="entry", data={"api_key": "test", "account_number": "test", "capability_type": "SMART_METER"})
    coordinator = MagicMock()
    async def refresh():
        return await coordinator_factory.call_args.kwargs["update_method"]()
    coordinator.async_config_entry_first_refresh = refresh
    with patch("custom_components.severn_trent.SevernTrentAPI", return_value=api), patch(
        "custom_components.severn_trent.DataUpdateCoordinator", return_value=coordinator,
    ) as coordinator_factory:
        if should_fail:
            with pytest.raises(UpdateFailed, match="No account or meter data"):
                await async_setup_entry(hass, entry)
            api.close.assert_called_once()
        else:
            assert await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_unload_closes_api_session():
    api = MagicMock()
    hass = MagicMock()
    hass.data = {"severn_trent": {"entry": {"api": api}}}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.async_add_executor_job = AsyncMock()
    assert await async_unload_entry(hass, SimpleNamespace(entry_id="entry"))
    hass.async_add_executor_job.assert_awaited_once_with(api.close)
    assert hass.data["severn_trent"] == {}

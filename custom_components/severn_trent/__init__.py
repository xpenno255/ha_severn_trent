"""The Severn Trent Water integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SevernTrentAPI
from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_MARKET_SUPPLY_POINT_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Severn Trent from a config entry."""
    _LOGGER.info("Setting up Severn Trent integration")
    _LOGGER.debug(
        "Config entry data: %s",
        {k: ("***" if k == CONF_API_KEY else v) for k, v in entry.data.items()},
    )

    api_key = entry.data.get(CONF_API_KEY)
    if not api_key:
        _LOGGER.error("Missing API key; reauthentication required")
        raise ConfigEntryAuthFailed("Missing API key")

    api = SevernTrentAPI(
        api_key=api_key,
        account_number=entry.data[CONF_ACCOUNT_NUMBER],
        market_supply_point_id=entry.data.get(CONF_MARKET_SUPPLY_POINT_ID),
        device_id=entry.data.get(CONF_DEVICE_ID),
    )
    
    _LOGGER.info("API object created, attempting authentication")
    
    # Authenticate
    if not await hass.async_add_executor_job(api.authenticate):
        _LOGGER.error("Authentication failed during setup")
        raise ConfigEntryAuthFailed("Authentication failed")
    
    _LOGGER.info("Authentication successful during setup")
    
    async def async_update_data():
        """Fetch data from API."""
        try:
            # Fetch manual readings first to get official reading date
            manual_data = await hass.async_add_executor_job(api.get_manual_meter_readings)

            # Get official reading date for smart meter data fetching
            official_reading_date = None
            if manual_data:
                official_reading_date = manual_data.get("reading_date")

            # Fetch smart meter readings with official date for partial month handling
            smart_data = await hass.async_add_executor_job(
                api.get_meter_readings, official_reading_date
            )

            if not smart_data and not manual_data:
                _LOGGER.warning("No data returned from API")

            # Combine both datasets
            return {
                "smart_meter": smart_data,
                "manual_meter": manual_data
            }
        except Exception as err:
            _LOGGER.error("Error in update: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}")
    
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="severn_trent",
        update_method=async_update_data,
        update_interval=timedelta(hours=1),  # Update every hour for testing
    )
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

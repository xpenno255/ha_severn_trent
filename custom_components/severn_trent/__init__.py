"""The Severn Trent Water integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .api import SevernTrentAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Severn Trent from a config entry."""
    _LOGGER.info("Setting up Severn Trent integration")
    _LOGGER.debug("Config entry data: %s", {k: v if k != "password" else "***" for k, v in entry.data.items()})
    
    api = SevernTrentAPI(
        email=entry.data["email"],
        password=entry.data["password"],
        account_number=entry.data["account_number"],
        market_supply_point_id=entry.data.get("market_supply_point_id"),
        device_id=entry.data.get("device_id")
    )
    
    _LOGGER.info("API object created, attempting authentication")
    
    # Authenticate
    if not await hass.async_add_executor_job(api.authenticate):
        _LOGGER.error("Authentication failed during setup")
        return False
    
    _LOGGER.info("Authentication successful during setup")
    
    async def async_update_data():
        """Fetch data from API."""
        try:
            # Fetch both smart meter and manual readings
            smart_data = await hass.async_add_executor_job(api.get_meter_readings)
            manual_data = await hass.async_add_executor_job(api.get_manual_meter_readings)
            
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
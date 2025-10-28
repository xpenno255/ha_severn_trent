"""The Severn Trent Water integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .api import SevernTrentAPI
from .coordinator import SevernTrentDataCoordinator

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
    
    # Create coordinator
    coordinator = SevernTrentDataCoordinator(
        hass=hass,
        api=api,
        account_number=entry.data["account_number"]
    )
    
    # Perform first refresh
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }
    
    # Backfill historical data if requested
    if entry.data.get("backfill_on_setup", False):
        _LOGGER.info("Backfill requested, starting historical data import")
        await coordinator.backfill_historical_data()
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def handle_backfill(call: ServiceCall) -> None:
        """Handle the backfill service call."""
        _LOGGER.info("Backfill service called")
        
        # Find the coordinator for this account
        account_number = call.data.get("account_number")
        
        if account_number:
            # Find entry with matching account number
            for entry_id, data in hass.data[DOMAIN].items():
                if isinstance(data, dict) and data.get("coordinator"):
                    coord = data["coordinator"]
                    if coord.account_number == account_number:
                        await coord.backfill_historical_data()
                        _LOGGER.info("Backfill completed for account %s", account_number)
                        return
            
            _LOGGER.error("Could not find account %s", account_number)
        else:
            # Backfill all accounts
            for entry_id, data in hass.data[DOMAIN].items():
                if isinstance(data, dict) and data.get("coordinator"):
                    coord = data["coordinator"]
                    await coord.backfill_historical_data()
                    _LOGGER.info("Backfill completed for account %s", coord.account_number)
    
    # Register the backfill service
    hass.services.async_register(
        DOMAIN,
        "backfill_history",
        handle_backfill,
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

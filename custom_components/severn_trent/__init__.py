"""The Severn Trent Water integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .api import SevernTrentAPI, AuthenticationError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Severn Trent from a config entry."""
    _LOGGER.info("Setting up Severn Trent integration")
    _LOGGER.debug(
        "Config entry data: %s",
        {k: v if k not in ("refresh_token",) else "***" for k, v in entry.data.items()},
    )

    api = SevernTrentAPI(
        email=entry.data[CONF_EMAIL],
        account_number=entry.data["account_number"],
        market_supply_point_id=entry.data.get("market_supply_point_id"),
        device_id=entry.data.get("device_id"),
        refresh_token=entry.data.get("refresh_token"),
        refresh_token_expires_at=entry.data.get("refresh_token_expires_at"),
    )

    _LOGGER.info("API object created with stored refresh token")

    # Try to refresh the JWT token on startup
    try:
        await api.refresh_jwt_token()
        _LOGGER.info("Successfully refreshed JWT token during setup")
    except AuthenticationError as err:
        _LOGGER.error("Authentication failed during setup: %s", err)
        raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.") from err

    async def async_update_data():
        """Fetch data from API."""
        try:
            # Fetch both smart meter and manual readings
            smart_data = await api.get_meter_readings()
            manual_data = await api.get_manual_meter_readings()

            if not smart_data and not manual_data:
                _LOGGER.warning("No data returned from API")

            # Combine both datasets
            return {"smart_meter": smart_data, "manual_meter": manual_data}
        except AuthenticationError as err:
            _LOGGER.error("Authentication error in update: %s", err)
            raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.") from err
        except Exception as err:
            _LOGGER.error("Error in update: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
    
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
"""The Yorkshire Water integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    YorkshireWaterAPI,
    YorkshireWaterAuthError,
    YorkshireWaterEndpointNotConfiguredError,
    YorkshireWaterError,
    YorkshireWaterExpiredSessionError,
)
from .const import (
    CONF_ACCOUNT_ID,
    CONF_METER_ID,
    CONF_SESSION_TOKEN,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yorkshire Water from a config entry."""
    _LOGGER.info("Setting up Yorkshire Water integration")
    _LOGGER.debug("Config entry data: %s", YorkshireWaterAPI.redact(dict(entry.data)))

    session_token = entry.data.get(CONF_SESSION_TOKEN)
    if not session_token:
        raise ConfigEntryAuthFailed("Missing Yorkshire Water session token")

    api = YorkshireWaterAPI(
        async_get_clientsession(hass),
        session_token=session_token,
        account_id=entry.data.get(CONF_ACCOUNT_ID),
        meter_id=entry.data.get(CONF_METER_ID),
    )

    async def async_update_data() -> dict:
        """Fetch data from Yorkshire Water."""
        try:
            return await api.async_fetch_usage_summary()
        except (YorkshireWaterExpiredSessionError, YorkshireWaterAuthError) as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except YorkshireWaterEndpointNotConfiguredError as err:
            _LOGGER.warning("%s", err)
            return {
                "status": "api_discovery_required",
                "status_detail": str(err),
                "account_id": api.account_id,
                "meter_id": api.meter_id,
            }
        except YorkshireWaterError as err:
            raise UpdateFailed(f"Error communicating with Yorkshire Water: {err}") from err

    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
    )

    # Avoid blocking setup while the Yorkshire Water endpoint contract is still
    # being discovered; sensors will show unavailable with a clear coordinator
    # error until the API layer is completed.
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

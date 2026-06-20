"""The Yorkshire Water integration."""

from __future__ import annotations

from datetime import timedelta
import inspect
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    YorkshireWaterAPI,
    YorkshireWaterAuthError,
    YorkshireWaterEndpointNotConfiguredError,
    YorkshireWaterError,
    YorkshireWaterExpiredSessionError,
    YorkshireWaterRefreshUnavailableError,
    build_expired_token_status_data,
)
from .const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_REFERENCE,
    CONF_BEARER_TOKEN,
    CONF_METER_ID,
    CONF_METER_REFERENCE,
    CONF_REFRESH_TOKEN,
    CONF_SESSION_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
)
from .statistics_import import (
    SERVICE_IMPORT_STATISTICS,
    async_handle_import_statistics,
    build_import_statistics_service_schema,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

DATA_IMPORT_STATISTICS_SERVICE_REGISTERED = "import_statistics_service_registered"


async def async_start_reauth_safely(
    entry: ConfigEntry,
    hass: HomeAssistant,
    logger: logging.Logger = _LOGGER,
) -> bool:
    """Start Home Assistant reauth when available without breaking refresh."""
    start_reauth = getattr(entry, "async_start_reauth", None)
    if start_reauth is None:
        logger.debug("Yorkshire Water reauthentication helper is not available")
        return False

    try:
        result = start_reauth(hass)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.warning(
            "Unable to start Yorkshire Water reauthentication flow",
            exc_info=True,
        )
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yorkshire Water from a config entry."""
    _LOGGER.info("Setting up Yorkshire Water integration")
    _LOGGER.debug("Config entry data: %s", YorkshireWaterAPI.redact(dict(entry.data)))

    bearer_token = entry.data.get(CONF_BEARER_TOKEN) or entry.data.get(CONF_SESSION_TOKEN)

    api = YorkshireWaterAPI(
        async_get_clientsession(hass),
        session_token=bearer_token,
        account_id=entry.data.get(CONF_ACCOUNT_ID),
        meter_id=entry.data.get(CONF_METER_ID),
        bearer_token=bearer_token,
        account_reference=entry.data.get(CONF_ACCOUNT_REFERENCE),
        meter_reference=entry.data.get(CONF_METER_REFERENCE),
        token_expires_at=entry.data.get(CONF_TOKEN_EXPIRES_AT),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
    )
    last_successful_data: dict | None = None
    reauth_started = False

    async def async_start_reauth_once() -> None:
        """Start Home Assistant reauth once when supported by this HA version."""
        nonlocal reauth_started
        if reauth_started:
            return
        reauth_started = True
        await async_start_reauth_safely(entry, hass)

    async def async_update_data() -> dict:
        """Fetch data from Yorkshire Water."""
        nonlocal last_successful_data
        try:
            data = await api.async_fetch_usage_summary()
            last_successful_data = data
            if auth_update := api.consume_pending_auth_update():
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_BEARER_TOKEN: auth_update["access_token"],
                        CONF_REFRESH_TOKEN: auth_update["refresh_token"],
                        CONF_TOKEN_EXPIRES_AT: auth_update["token_expires_at"],
                    },
                )
            return data
        except YorkshireWaterRefreshUnavailableError as err:
            _LOGGER.warning(
                "Yorkshire Water access token expired and refresh is unavailable; "
                "reauthentication is required"
            )
            await async_start_reauth_once()
            return build_expired_token_status_data(
                account_configured=bool(api.account_reference),
                meter_configured=bool(api.meter_reference),
                last_successful_update=(last_successful_data or {}).get(
                    "last_successful_update"
                ),
                latest_data_date=(last_successful_data or {}).get("latest_data_date"),
                latest_update_date=(last_successful_data or {}).get("latest_update_date"),
            )
        except YorkshireWaterExpiredSessionError as err:
            _LOGGER.warning("%s", err)
            await async_start_reauth_once()
            return build_expired_token_status_data(
                account_configured=bool(api.account_reference),
                meter_configured=bool(api.meter_reference),
                last_successful_update=(last_successful_data or {}).get(
                    "last_successful_update"
                ),
                latest_data_date=(last_successful_data or {}).get("latest_data_date"),
                latest_update_date=(last_successful_data or {}).get("latest_update_date"),
                refresh_available=bool(api.refresh_token),
            )
        except YorkshireWaterAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except YorkshireWaterEndpointNotConfiguredError as err:
            _LOGGER.warning("%s", err)
            return {
                "status": "api_discovery_required",
                "status_detail": str(err),
                "token_status": "token_valid" if bearer_token else "reauth_required",
                "account_configured": bool(api.account_reference),
                "meter_configured": bool(api.meter_reference),
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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }
    async_register_import_statistics_service(hass)

    # Avoid blocking setup while the Yorkshire Water endpoint contract is still
    # being discovered; sensors will show unavailable with a clear coordinator
    # error until the API layer is completed.
    await coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def async_register_import_statistics_service(hass: HomeAssistant) -> None:
    """Register the Yorkshire Water historical statistics import service once."""
    hass.data.setdefault(DOMAIN, {})
    if hass.data[DOMAIN].get(DATA_IMPORT_STATISTICS_SERVICE_REGISTERED):
        return

    hass.data[DOMAIN]["statistics_import_logger"] = _LOGGER

    async def async_service_handler(call) -> dict:
        """Handle the import_statistics service call."""
        return await async_handle_import_statistics(hass, call)

    hass.services.async_register(
        DOMAIN,
        "import_statistics",
        async_service_handler,
        schema=build_import_statistics_service_schema(),
        supports_response=SupportsResponse.ONLY,
    )
    hass.data[DOMAIN][DATA_IMPORT_STATISTICS_SERVICE_REGISTERED] = True
    _LOGGER.info("Registered Yorkshire Water import_statistics service")


def async_unregister_import_statistics_service(hass: HomeAssistant) -> None:
    """Unregister the Yorkshire Water historical statistics import service."""
    if not hass.data.get(DOMAIN, {}).pop(
        DATA_IMPORT_STATISTICS_SERVICE_REGISTERED,
        False,
    ):
        return
    hass.data[DOMAIN].pop("statistics_import_logger", None)
    hass.services.async_remove(DOMAIN, SERVICE_IMPORT_STATISTICS)
    _LOGGER.info("Unregistered Yorkshire Water import_statistics service")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not any(
            isinstance(value, dict) and "api" in value
            for value in hass.data[DOMAIN].values()
        ):
            async_unregister_import_statistics_service(hass)

    return unload_ok

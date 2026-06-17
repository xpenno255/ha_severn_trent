"""Config flow for Yorkshire Water."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AUTH_TYPE_SESSION_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_AUTH_TYPE,
    CONF_METER_ID,
    CONF_SESSION_TOKEN,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class YorkshireWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yorkshire Water."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial temporary development auth step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session_token = user_input[CONF_SESSION_TOKEN].strip()
            account_id = user_input.get(CONF_ACCOUNT_ID, "").strip() or None
            meter_id = user_input.get(CONF_METER_ID, "").strip() or None

            if not session_token:
                errors["base"] = "invalid_auth"
            else:
                unique_id = meter_id or account_id or DEFAULT_NAME.lower().replace(" ", "_")
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title_detail = account_id or meter_id
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} ({title_detail})" if title_detail else DEFAULT_NAME,
                    data={
                        CONF_AUTH_TYPE: AUTH_TYPE_SESSION_TOKEN,
                        CONF_SESSION_TOKEN: session_token,
                        CONF_ACCOUNT_ID: account_id,
                        CONF_METER_ID: meter_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SESSION_TOKEN): str,
                    vol.Optional(CONF_ACCOUNT_ID): str,
                    vol.Optional(CONF_METER_ID): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Start a reauthentication flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id")
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update the temporary Yorkshire Water session token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session_token = user_input[CONF_SESSION_TOKEN].strip()
            if not session_token:
                errors["base"] = "invalid_auth"
            elif self._reauth_entry is None:
                _LOGGER.error("Reauthentication requested without a config entry")
                return self.async_abort(reason="unknown")
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_SESSION_TOKEN: session_token,
                    },
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_SESSION_TOKEN): str}),
            errors=errors,
        )

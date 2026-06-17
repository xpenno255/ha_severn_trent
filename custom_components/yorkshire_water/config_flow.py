"""Config flow for Yorkshire Water."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import (
    YorkshireWaterAuthError,
    YorkshireWaterExpiredSessionError,
    YorkshireWaterSchemaError,
    build_token_auth_data,
)
from .const import (
    AUTH_TYPE_BEARER_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_REFERENCE,
    CONF_AUTH_TYPE,
    CONF_BEARER_TOKEN,
    CONF_METER_ID,
    CONF_METER_REFERENCE,
    CONF_SESSION_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    CONF_TOKEN_RESPONSE_JSON,
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
            bearer_token = user_input.get(CONF_BEARER_TOKEN, "").strip() or None
            legacy_token = user_input.get(CONF_SESSION_TOKEN, "").strip() or None
            token_response_json = (
                user_input.get(CONF_TOKEN_RESPONSE_JSON, "").strip() or None
            )
            account_reference = (
                user_input.get(CONF_ACCOUNT_REFERENCE, "").strip()
                or user_input.get(CONF_ACCOUNT_ID, "").strip()
                or None
            )
            meter_reference = (
                user_input.get(CONF_METER_REFERENCE, "").strip()
                or user_input.get(CONF_METER_ID, "").strip()
                or None
            )

            try:
                auth_data = build_token_auth_data(
                    raw_access_token=bearer_token or legacy_token,
                    token_response_json=token_response_json,
                )
            except YorkshireWaterExpiredSessionError:
                errors["base"] = "token_expired"
            except YorkshireWaterAuthError as err:
                errors["base"] = (
                    "id_token_supplied"
                    if "id_token" in str(err)
                    else "invalid_auth"
                )
            except YorkshireWaterSchemaError:
                errors["base"] = "invalid_token_response"
            else:
                unique_source = meter_reference or account_reference
                unique_id = (
                    "yw_" + hashlib.sha256(unique_source.encode()).hexdigest()[:12]
                    if unique_source
                    else DEFAULT_NAME.lower().replace(" ", "_")
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_AUTH_TYPE: AUTH_TYPE_BEARER_TOKEN,
                        CONF_BEARER_TOKEN: auth_data["access_token"],
                        CONF_TOKEN_EXPIRES_AT: auth_data["token_expires_at"],
                        CONF_ACCOUNT_REFERENCE: account_reference,
                        CONF_METER_REFERENCE: meter_reference,
                        CONF_ACCOUNT_ID: account_reference,
                        CONF_METER_ID: meter_reference,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BEARER_TOKEN): str,
                    vol.Optional(CONF_TOKEN_RESPONSE_JSON): str,
                    vol.Optional(CONF_ACCOUNT_REFERENCE): str,
                    vol.Optional(CONF_METER_REFERENCE): str,
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
        """Update the temporary Yorkshire Water access token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            bearer_token = user_input.get(CONF_BEARER_TOKEN, "").strip() or None
            token_response_json = (
                user_input.get(CONF_TOKEN_RESPONSE_JSON, "").strip() or None
            )
            try:
                auth_data = build_token_auth_data(
                    raw_access_token=bearer_token,
                    token_response_json=token_response_json,
                )
            except YorkshireWaterExpiredSessionError:
                errors["base"] = "token_expired"
            except YorkshireWaterAuthError as err:
                errors["base"] = (
                    "id_token_supplied"
                    if "id_token" in str(err)
                    else "invalid_auth"
                )
            except YorkshireWaterSchemaError:
                errors["base"] = "invalid_token_response"
            else:
                if self._reauth_entry is None:
                    _LOGGER.error("Reauthentication requested without a config entry")
                    return self.async_abort(reason="unknown")
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_AUTH_TYPE: AUTH_TYPE_BEARER_TOKEN,
                        CONF_BEARER_TOKEN: auth_data["access_token"],
                        CONF_TOKEN_EXPIRES_AT: auth_data["token_expires_at"],
                    },
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BEARER_TOKEN): str,
                    vol.Optional(CONF_TOKEN_RESPONSE_JSON): str,
                }
            ),
            errors=errors,
        )

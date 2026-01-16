"""Config flow for Severn Trent Water integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import SevernTrentAPI
from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_API_KEY,
    CONF_BROWSER_TOKEN,
    CONF_DEVICE_ID,
    CONF_MARKET_SUPPLY_POINT_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class SevernTrentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Severn Trent Water."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.api = None
        self.account_numbers = []
        self.api_key = None
        self._reauth_entry = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - browser token to generate API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                browser_token = user_input[CONF_BROWSER_TOKEN].strip()
                if not browser_token:
                    errors["base"] = "invalid_auth"
                else:
                    self.api_key = await self.hass.async_add_executor_job(
                        SevernTrentAPI.generate_api_key,
                        browser_token,
                    )

                    if not self.api_key:
                        errors["base"] = "cannot_generate_api_key"
                    else:
                        # Create API client and authenticate
                        self.api = SevernTrentAPI(api_key=self.api_key)

                        auth_success = await self.hass.async_add_executor_job(
                            self.api.authenticate
                        )

                        if not auth_success:
                            errors["base"] = "invalid_auth"
                        else:
                            # Fetch account numbers
                            self.account_numbers = await self.hass.async_add_executor_job(
                                self.api.fetch_account_numbers
                            )

                            if not self.account_numbers:
                                errors["base"] = "no_accounts"
                            elif len(self.account_numbers) == 1:
                                # Single account - proceed directly to setup
                                account_number = self.account_numbers[0]
                                self.api.account_number = account_number

                                # Fetch meter identifiers
                                identifiers_success = (
                                    await self.hass.async_add_executor_job(
                                        self.api._fetch_meter_identifiers
                                    )
                                )

                                if not identifiers_success:
                                    errors["base"] = "cannot_fetch_meters"
                                else:
                                    # Create entry
                                    await self.async_set_unique_id(account_number)
                                    self._abort_if_unique_id_configured()

                                    return self.async_create_entry(
                                        title=f"Severn Trent ({account_number})",
                                        data={
                                            CONF_API_KEY: self.api_key,
                                            CONF_ACCOUNT_NUMBER: account_number,
                                            CONF_MARKET_SUPPLY_POINT_ID: self.api.market_supply_point_id,
                                            CONF_DEVICE_ID: self.api.device_id,
                                        },
                                    )
                            else:
                                # Multiple accounts - show selection step
                                return await self.async_step_account_selection()
                        
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROWSER_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_account_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle account selection for users with multiple accounts."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                account_number = user_input[CONF_ACCOUNT_NUMBER]
                self.api.account_number = account_number
                
                # Fetch meter identifiers for selected account
                identifiers_success = await self.hass.async_add_executor_job(
                    self.api._fetch_meter_identifiers
                )
                
                if not identifiers_success:
                    errors["base"] = "cannot_fetch_meters"
                else:
                    # Create entry
                    await self.async_set_unique_id(account_number)
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"Severn Trent ({account_number})",
                        data={
                            CONF_ACCOUNT_NUMBER: account_number,
                            CONF_API_KEY: self.api_key,
                            CONF_MARKET_SUPPLY_POINT_ID: self.api.market_supply_point_id,
                            CONF_DEVICE_ID: self.api.device_id,
                        },
                    )
                    
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="account_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_NUMBER): vol.In(self.account_numbers),
                }
            ),
            errors=errors,
            description_placeholders={
                "num_accounts": str(len(self.account_numbers))
            }
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Start a reauthentication flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id")
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauthentication and update the API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            browser_token = user_input[CONF_BROWSER_TOKEN].strip()
            if not browser_token:
                errors["base"] = "invalid_auth"
            else:
                api_key = await self.hass.async_add_executor_job(
                    SevernTrentAPI.generate_api_key,
                    browser_token,
                )

                if not api_key:
                    errors["base"] = "cannot_generate_api_key"
                else:
                    if self._reauth_entry is None:
                        return self.async_abort(reason="unknown")

                    updated_data = {
                        CONF_API_KEY: api_key,
                        CONF_ACCOUNT_NUMBER: self._reauth_entry.data.get(
                            CONF_ACCOUNT_NUMBER
                        ),
                        CONF_MARKET_SUPPLY_POINT_ID: self._reauth_entry.data.get(
                            CONF_MARKET_SUPPLY_POINT_ID
                        ),
                        CONF_DEVICE_ID: self._reauth_entry.data.get(CONF_DEVICE_ID),
                    }
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=updated_data,
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_BROWSER_TOKEN): str}),
            errors=errors,
        )

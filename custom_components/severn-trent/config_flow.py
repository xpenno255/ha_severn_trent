"""Config flow for Severn Trent Water integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .api import SevernTrentAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNT_NUMBER = "account_number"

class SevernTrentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Severn Trent Water."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.api = None
        self.account_numbers = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - email and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Create API client and authenticate
                self.api = SevernTrentAPI(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD]
                )
                
                auth_success = await self.hass.async_add_executor_job(self.api.authenticate)
                
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
                        identifiers_success = await self.hass.async_add_executor_job(
                            self.api._fetch_meter_identifiers
                        )
                        
                        if not identifiers_success:
                            errors["base"] = "cannot_fetch_meters"
                        else:
                            # Create entry
                            await self.async_set_unique_id(user_input[CONF_EMAIL])
                            self._abort_if_unique_id_configured()
                            
                            return self.async_create_entry(
                                title=f"Severn Trent ({account_number})",
                                data={
                                    CONF_EMAIL: user_input[CONF_EMAIL],
                                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                                    CONF_ACCOUNT_NUMBER: account_number,
                                    "market_supply_point_id": self.api.market_supply_point_id,
                                    "device_id": self.api.device_id,
                                },
                            )
                    else:
                        # Multiple accounts - show selection step
                        return await self.async_step_account_selection(user_input)
                        
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
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
                    await self.async_set_unique_id(self.api.email)
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"Severn Trent ({account_number})",
                        data={
                            CONF_EMAIL: self.api.email,
                            CONF_PASSWORD: self.api.password,
                            CONF_ACCOUNT_NUMBER: account_number,
                            "market_supply_point_id": self.api.market_supply_point_id,
                            "device_id": self.api.device_id,
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
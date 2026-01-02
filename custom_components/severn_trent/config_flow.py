"""Config flow for Severn Trent Water integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL
from homeassistant.data_entry_flow import FlowResult

from .api import SevernTrentAPI, AuthenticationError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNT_NUMBER = "account_number"
CONF_MAGIC_LINK = "magic_link"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_REFRESH_TOKEN_EXPIRES_AT = "refresh_token_expires_at"


class SevernTrentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Severn Trent Water."""

    VERSION = 2  # Incremented for new auth flow

    def __init__(self):
        """Initialize the config flow."""
        self.email = None
        self.api = None
        self.account_numbers = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - email entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]

            # Send magic link email
            success = await SevernTrentAPI.send_magic_link_email(self.email)

            if success:
                # Proceed to magic link step
                return await self.async_step_magic_link()
            else:
                errors["base"] = "cannot_send_email"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "info": "Enter your Severn Trent account email address. You will receive a magic link email to authenticate."
            },
        )

    async def async_step_magic_link(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle magic link URL input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            magic_link_url = user_input[CONF_MAGIC_LINK]

            # Extract token from URL
            magic_token = SevernTrentAPI.extract_token_from_url(magic_link_url)

            if not magic_token:
                errors["base"] = "invalid_magic_link"
            else:
                # Create temporary API client to exchange token
                self.api = SevernTrentAPI(email=self.email)

                # Exchange token for JWT
                exchange_success = await self.api.exchange_token_for_jwt(magic_token)

                if not exchange_success:
                    errors["base"] = "invalid_auth"
                else:
                    # Fetch account numbers
                    self.account_numbers = await self.api.fetch_account_numbers()

                    if not self.account_numbers:
                        errors["base"] = "no_accounts"
                    elif len(self.account_numbers) == 1:
                        # Single account - proceed directly to finalization
                        return await self._finalize_setup(self.account_numbers[0])
                    else:
                        # Multiple accounts - show selection
                        return await self.async_step_account_selection()

        return self.async_show_form(
            step_id="magic_link",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAGIC_LINK): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "email": self.email,
                "info": "Check your email and paste the magic link URL here. The link looks like: https://my-account.stwater.co.uk/?key=... or you can paste just the token.",
            },
        )

    async def async_step_account_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle account selection for users with multiple accounts."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account_number = user_input[CONF_ACCOUNT_NUMBER]
            return await self._finalize_setup(account_number)

        return self.async_show_form(
            step_id="account_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_NUMBER): vol.In(self.account_numbers),
                }
            ),
            errors=errors,
            description_placeholders={"num_accounts": str(len(self.account_numbers))},
        )

    async def _finalize_setup(self, account_number: str) -> FlowResult:
        """Finalize setup by fetching meter identifiers and creating entry."""
        self.api.account_number = account_number

        # Fetch meter identifiers for selected account
        identifiers_success = await self.api._fetch_meter_identifiers()

        if not identifiers_success:
            return self.async_abort(reason="cannot_fetch_meters")

        # Create entry
        await self.async_set_unique_id(self.email)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Severn Trent ({account_number})",
            data={
                CONF_EMAIL: self.email,
                CONF_ACCOUNT_NUMBER: account_number,
                "market_supply_point_id": self.api.market_supply_point_id,
                "device_id": self.api.device_id,
                CONF_REFRESH_TOKEN: self.api.refresh_token,
                CONF_REFRESH_TOKEN_EXPIRES_AT: self.api.refresh_token_expires_at,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth flow when tokens expire."""
        self.email = entry_data[CONF_EMAIL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirmation - send new magic link."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Send magic link email
            success = await SevernTrentAPI.send_magic_link_email(self.email)

            if success:
                return await self.async_step_reauth_magic_link()
            else:
                errors["base"] = "cannot_send_email"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "email": self.email,
                "info": "Your authentication has expired. Click Submit to receive a new magic link email.",
            },
        )

    async def async_step_reauth_magic_link(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle magic link input during reauth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            magic_link_url = user_input[CONF_MAGIC_LINK]

            # Extract token from URL
            magic_token = SevernTrentAPI.extract_token_from_url(magic_link_url)

            if not magic_token:
                errors["base"] = "invalid_magic_link"
            else:
                # Get the existing entry
                existing_entry = None
                for entry in self._async_current_entries():
                    if entry.data.get(CONF_EMAIL) == self.email:
                        existing_entry = entry
                        break

                if not existing_entry:
                    return self.async_abort(reason="reauth_failed")

                # Create temporary API client to exchange token
                api = SevernTrentAPI(email=self.email)

                # Exchange token for JWT
                exchange_success = await api.exchange_token_for_jwt(magic_token)

                if not exchange_success:
                    errors["base"] = "invalid_auth"
                else:
                    # Update the config entry with new tokens
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data={
                            **existing_entry.data,
                            CONF_REFRESH_TOKEN: api.refresh_token,
                            CONF_REFRESH_TOKEN_EXPIRES_AT: api.refresh_token_expires_at,
                        },
                    )

                    # Reload the integration
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)

                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_magic_link",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAGIC_LINK): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "email": self.email,
                "info": "Check your email and paste the magic link URL here.",
            },
        )

"""Config flow for Yorkshire Water."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    YorkshireWaterAPI,
    YorkshireWaterAuthError,
    YorkshireWaterExpiredSessionError,
    YorkshireWaterOfflineAccessUnsupportedError,
    YorkshireWaterSchemaError,
    build_oauth_authorization_params,
    build_token_auth_data,
    extract_authorization_code,
    generate_pkce_code_challenge,
    validate_oauth_state,
)
from .const import (
    AUTH_TYPE_BEARER_TOKEN,
    AUTH_TYPE_OAUTH_PKCE,
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_REFERENCE,
    CONF_AUTH_TYPE,
    CONF_BEARER_TOKEN,
    CONF_METER_ID,
    CONF_METER_REFERENCE,
    CONF_OAUTH_AUTHORIZATION_CODE,
    CONF_OAUTH_CALLBACK_URL,
    CONF_OAUTH_CODE_VERIFIER,
    CONF_OAUTH_REQUEST_OFFLINE_ACCESS,
    CONF_REFRESH_TOKEN,
    CONF_SESSION_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    CONF_TOKEN_RESPONSE_JSON,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def build_experimental_oauth_authorization_params(
    code_verifier: str,
    state: str,
    *,
    request_offline_access: bool = False,
) -> dict[str, str]:
    """Build experimental OAuth params for user-guided portal testing."""
    return build_oauth_authorization_params(
        generate_pkce_code_challenge(code_verifier),
        state,
        include_offline_access=request_offline_access,
    )


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
            oauth_callback = (
                user_input.get(CONF_OAUTH_CALLBACK_URL, "").strip() or None
            )
            oauth_code = (
                user_input.get(CONF_OAUTH_AUTHORIZATION_CODE, "").strip() or None
            )
            oauth_code_verifier = (
                user_input.get(CONF_OAUTH_CODE_VERIFIER, "").strip() or None
            )
            oauth_request_offline_access = bool(
                user_input.get(CONF_OAUTH_REQUEST_OFFLINE_ACCESS, False)
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
                auth_data, auth_type = await self._async_build_auth_data(
                    raw_access_token=bearer_token or legacy_token,
                    token_response_json=token_response_json,
                    oauth_callback_or_code=oauth_callback or oauth_code,
                    oauth_code_verifier=oauth_code_verifier,
                    oauth_request_offline_access=oauth_request_offline_access,
                )
            except YorkshireWaterExpiredSessionError:
                errors["base"] = "token_expired"
            except YorkshireWaterOfflineAccessUnsupportedError:
                errors["base"] = "offline_access_not_supported"
            except YorkshireWaterAuthError as err:
                errors["base"] = (
                    "id_token_supplied"
                    if "id_token" in str(err)
                    else "invalid_oauth"
                    if oauth_callback or oauth_code or oauth_code_verifier
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
                        CONF_AUTH_TYPE: auth_type,
                        CONF_BEARER_TOKEN: auth_data["access_token"],
                        CONF_REFRESH_TOKEN: auth_data.get("refresh_token"),
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
                    vol.Optional(CONF_OAUTH_CALLBACK_URL): str,
                    vol.Optional(CONF_OAUTH_AUTHORIZATION_CODE): str,
                    vol.Optional(CONF_OAUTH_CODE_VERIFIER): str,
                    vol.Optional(
                        CONF_OAUTH_REQUEST_OFFLINE_ACCESS,
                        default=False,
                    ): bool,
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
            oauth_callback = (
                user_input.get(CONF_OAUTH_CALLBACK_URL, "").strip() or None
            )
            oauth_code = (
                user_input.get(CONF_OAUTH_AUTHORIZATION_CODE, "").strip() or None
            )
            oauth_code_verifier = (
                user_input.get(CONF_OAUTH_CODE_VERIFIER, "").strip() or None
            )
            oauth_request_offline_access = bool(
                user_input.get(CONF_OAUTH_REQUEST_OFFLINE_ACCESS, False)
            )
            try:
                auth_data, auth_type = await self._async_build_auth_data(
                    raw_access_token=bearer_token,
                    token_response_json=token_response_json,
                    oauth_callback_or_code=oauth_callback or oauth_code,
                    oauth_code_verifier=oauth_code_verifier,
                    oauth_request_offline_access=oauth_request_offline_access,
                )
            except YorkshireWaterExpiredSessionError:
                errors["base"] = "token_expired"
            except YorkshireWaterOfflineAccessUnsupportedError:
                errors["base"] = "offline_access_not_supported"
            except YorkshireWaterAuthError as err:
                errors["base"] = (
                    "id_token_supplied"
                    if "id_token" in str(err)
                    else "invalid_oauth"
                    if oauth_callback or oauth_code or oauth_code_verifier
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
                        CONF_AUTH_TYPE: auth_type,
                        CONF_BEARER_TOKEN: auth_data["access_token"],
                        CONF_REFRESH_TOKEN: auth_data.get("refresh_token"),
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
                    vol.Optional(CONF_OAUTH_CALLBACK_URL): str,
                    vol.Optional(CONF_OAUTH_AUTHORIZATION_CODE): str,
                    vol.Optional(CONF_OAUTH_CODE_VERIFIER): str,
                    vol.Optional(
                        CONF_OAUTH_REQUEST_OFFLINE_ACCESS,
                        default=False,
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def _async_build_auth_data(
        self,
        *,
        raw_access_token: str | None = None,
        token_response_json: str | None = None,
        oauth_callback_or_code: str | None = None,
        oauth_code_verifier: str | None = None,
        oauth_request_offline_access: bool = False,
    ) -> tuple[dict[str, Any], str]:
        """Build auth data from manual beta or experimental OAuth inputs."""
        if oauth_callback_or_code or oauth_code_verifier:
            if not oauth_callback_or_code or not oauth_code_verifier:
                raise YorkshireWaterAuthError(
                    "Yorkshire Water OAuth code and code verifier are required"
                )
            code, returned_state = extract_authorization_code(oauth_callback_or_code)
            expected_state = self.context.get("oauth_state")
            validate_oauth_state(returned_state, expected_state)
            if oauth_request_offline_access:
                build_experimental_oauth_authorization_params(
                    oauth_code_verifier,
                    expected_state or "",
                    request_offline_access=True,
                )
            api = YorkshireWaterAPI(
                async_get_clientsession(self.hass),
                session_token=None,
            )
            auth_data = await api.async_exchange_authorization_code(
                code,
                oauth_code_verifier,
            )
            return auth_data, AUTH_TYPE_OAUTH_PKCE

        return (
            build_token_auth_data(
                raw_access_token=raw_access_token,
                token_response_json=token_response_json,
            ),
            AUTH_TYPE_BEARER_TOKEN,
        )

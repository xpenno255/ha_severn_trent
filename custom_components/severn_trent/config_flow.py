"""Account, meter selection and verified credential recovery."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from .api import SevernTrentAPI, APIError, AuthenticationError
from .const import (DOMAIN, CONF_API_KEY, CONF_BROWSER_TOKEN, CONF_ACCOUNT_NUMBER,
                    CONF_DEVICE_ID, CONF_MARKET_SUPPLY_POINT_ID, CONF_CAPABILITY_TYPE)


class SevernTrentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.api = None
        self.api_key = None
        self.account_numbers = []
        self.meters = []
        self._reauth_entry = None

    async def _connect(self, user_input):
        key = user_input.get(CONF_API_KEY, '').strip()
        existing = user_input.get('existing_account')
        if existing and not key:
            entry = self.hass.config_entries.async_get_entry(existing)
            if entry and entry.domain == DOMAIN:
                key = entry.data[CONF_API_KEY]
        if not key:
            token = user_input.get(CONF_BROWSER_TOKEN, '').strip()
            if not token:
                raise AuthenticationError('Enter a key, token, or existing connection')
            key = await self.hass.async_add_executor_job(SevernTrentAPI.generate_api_key, token)
        if not key:
            raise AuthenticationError('Unable to generate key')
        self.api_key = key
        self.api = SevernTrentAPI(api_key=key)
        if not await self.hass.async_add_executor_job(self.api.authenticate):
            raise self.api.auth_error or AuthenticationError('Authentication failed')
        self.account_numbers = await self.hass.async_add_executor_job(self.api.fetch_account_numbers)
        if not self.account_numbers:
            raise APIError('No accounts returned')

    async def _close(self):
        if self.api:
            await self.hass.async_add_executor_job(self.api.close)

    def _credential_schema(self):
        fields = {vol.Optional(CONF_API_KEY): str, vol.Optional(CONF_BROWSER_TOKEN): str}
        entries = {e.entry_id: e.title for e in self._async_current_entries()}
        if entries and not self._reauth_entry:
            fields[vol.Optional('existing_account')] = vol.In(entries)
        return vol.Schema(fields)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._connect(user_input)
                if len(self.account_numbers) == 1:
                    return await self.async_step_account_selection({CONF_ACCOUNT_NUMBER: self.account_numbers[0]})
                return await self.async_step_account_selection()
            except AuthenticationError:
                errors['base'] = 'invalid_auth'
            except APIError:
                errors['base'] = 'cannot_connect'
            finally:
                await self._close()
        return self.async_show_form(step_id='user', data_schema=self._credential_schema(), errors=errors)

    async def async_step_account_selection(self, user_input=None):
        errors = {}
        if user_input is not None:
            account = user_input[CONF_ACCOUNT_NUMBER]
            if account not in self.account_numbers:
                errors['base'] = 'no_accounts'
            else:
                await self.async_set_unique_id(account)
                self._abort_if_unique_id_configured()
                self.api.account_number = account
                try:
                    self.meters = await self.hass.async_add_executor_job(self.api.get_available_meters)
                    if len(self.meters) == 1:
                        return await self.async_step_meter_selection({CONF_DEVICE_ID: self.meters[0]['serialNumber']})
                    if self.meters:
                        return await self.async_step_meter_selection()
                    errors['base'] = 'cannot_fetch_meters'
                except AuthenticationError:
                    errors['base'] = 'invalid_auth'
                except APIError:
                    errors['base'] = 'cannot_connect'
                finally:
                    await self._close()
        return self.async_show_form(step_id='account_selection',
            data_schema=vol.Schema({vol.Required(CONF_ACCOUNT_NUMBER): vol.In(self.account_numbers)}),
            errors=errors, description_placeholders={'num_accounts':str(len(self.account_numbers))})

    async def async_step_meter_selection(self, user_input=None):
        if user_input is not None:
            selected = next((m for m in self.meters if m['serialNumber'] == user_input[CONF_DEVICE_ID]), None)
            if selected:
                return self.async_create_entry(title=f'Severn Trent ({self.api.account_number})', data={
                    CONF_ACCOUNT_NUMBER:self.api.account_number, CONF_API_KEY:self.api_key,
                    CONF_DEVICE_ID:selected['serialNumber'],
                    CONF_MARKET_SUPPLY_POINT_ID:selected['meterPointReference'],
                    CONF_CAPABILITY_TYPE:selected.get('capabilityType')})
        return self.async_show_form(step_id='meter_selection', data_schema=vol.Schema({
            vol.Required(CONF_DEVICE_ID): vol.In({m['serialNumber']:f"{m['serialNumber']} ({m.get('capabilityType', 'meter')})" for m in self.meters})}))

    async def async_step_reauth(self, entry_data):
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context['entry_id'])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._connect(user_input)
                entry = self._reauth_entry
                if entry.data[CONF_ACCOUNT_NUMBER] not in self.account_numbers:
                    errors['base'] = 'wrong_account'
                else:
                    old_key = entry.data.get(CONF_API_KEY)
                    siblings = [e for e in self._async_current_entries()
                                if e.data.get(CONF_API_KEY) == old_key and
                                e.data.get(CONF_ACCOUNT_NUMBER) in self.account_numbers]
                    for sibling in siblings:
                        self.hass.config_entries.async_update_entry(sibling, data={**sibling.data, CONF_API_KEY:self.api_key})
                    for sibling in siblings:
                        await self.hass.config_entries.async_reload(sibling.entry_id)
                    return self.async_abort(reason='reauth_successful')
            except AuthenticationError:
                errors['base'] = 'invalid_auth'
            except APIError:
                errors['base'] = 'cannot_connect'
            finally:
                await self._close()
        return self.async_show_form(step_id='reauth_confirm', data_schema=self._credential_schema(), errors=errors)

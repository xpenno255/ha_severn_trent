"""Allowlisted diagnostics: no credentials, account IDs or raw supplier payloads."""
from __future__ import annotations

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime['coordinator']
    data = coordinator.data or {}
    smart = data.get('smart_meter') or {}
    history = data.get('history') or {}
    return {
        'last_update_success': coordinator.last_update_success,
        'capability_type': (data.get('meter_info') or {}).get('capability_type'),
        'daily_data': {key: smart.get(key) for key in (
            'latest_daily_date', 'days_in_average', 'days_in_current_week',
            'days_expected_current_week', 'days_in_previous_week')},
        'history': {key: history.get(key) for key in (
            'status', 'days_imported', 'latest_day', 'missing_recent_days',
            'backfill_start', 'backfill_cursor')},
        'datasets_available': {key: bool(data.get(key)) for key in (
            'smart_meter', 'manual_meter', 'balance', 'payment_schedule', 'next_payment')},
    }

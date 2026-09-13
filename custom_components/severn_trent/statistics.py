"""Persistent, correction-aware daily water history for the Energy Dashboard."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import logging

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.helpers.storage import Store

from .api import APIError, WATER_TIME_ZONE
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def build_statistics(days: dict[str, float]) -> list[dict]:
    """Put each known day's total in its final hour; never invent hourly usage.

    Midnight carries the preceding sum. The preceding day's final hour seeds
    the baseline so HA can calculate the first day's difference. Replaying
    from a changed date also repairs every subsequent cumulative sum.
    """
    if not days:
        return []
    ordered = sorted(days)
    first = datetime.fromisoformat(ordered[0]).replace(tzinfo=WATER_TIME_ZONE).astimezone(timezone.utc)
    rows = [{"start": first - timedelta(hours=1), "sum": 0.0, "state": 0.0}]
    total = 0.0
    for day in ordered:
        local = datetime.fromisoformat(day).replace(tzinfo=WATER_TIME_ZONE)
        rows.append({"start": local.astimezone(timezone.utc), "sum": round(total, 6), "state": round(total, 6)})
        total += days[day]
        last_hour = (local + timedelta(days=1)).astimezone(timezone.utc) - timedelta(hours=1)
        rows.append({"start": last_hour, "sum": round(total, 6), "state": round(total, 6)})
    return rows


class WaterStatistics:
    """Cache dated volumes, backfill a year, and revisit older corrections."""

    def __init__(self, hass, entry, api):
        self.hass, self.api = hass, api
        identity = f"{entry.data['account_number']}|{api.market_supply_point_id}|{api.device_id}"
        digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
        self.statistic_id = f"{DOMAIN}:water_{digest}"
        self.store = Store(hass, 1, f"{DOMAIN}.history_{digest}")
        self.cache = None
        self.replayed = False
        self.status = {}

    async def async_update(self):
        if 'recorder' not in self.hass.config.components:
            self.status = {"status": "recorder_disabled"}
            return
        today = datetime.now(WATER_TIME_ZONE).date()
        if self.cache is None:
            self.cache = await self.store.async_load() or {
                "days": {}, "start": (today - timedelta(days=365)).isoformat(),
                "cursor": (today - timedelta(days=365)).isoformat(),
            }
        days = dict(self.cache["days"])
        cursor = date.fromisoformat(self.cache["cursor"])
        if cursor >= today:
            cursor = date.fromisoformat(self.cache["start"])
        historical_end = min(cursor + timedelta(days=31), today)
        try:
            # Recent late readings are checked hourly; older history rotates in
            # month-sized requests, keeping each refresh bounded to two calls.
            recent = await self.hass.async_add_executor_job(
                self.api.get_daily_history, (today - timedelta(days=35)).isoformat(), today.isoformat())
            older = await self.hass.async_add_executor_job(
                self.api.get_daily_history, cursor.isoformat(), historical_end.isoformat())
        except (APIError, ValueError):
            self.status = {"status": "retrying", "statistic_id": self.statistic_id}
            _LOGGER.warning("Water history unavailable; retaining the last successful import")
            return
        days.update(older)
        days.update(recent)
        if days and (days != self.cache["days"] or not self.replayed):
            async_add_external_statistics(self.hass, {
                "statistic_id": self.statistic_id, "source": DOMAIN,
                "name": f"Severn Trent daily water ({self.api.device_id})",
                "unit_of_measurement": "m³", "unit_class": "volume",
                "mean_type": StatisticMeanType.NONE, "has_sum": True,
            }, build_statistics(days))
            self.replayed = True
        self.cache.update(days=days, cursor=historical_end.isoformat())
        await self.store.async_save(self.cache)
        recent_expected = {(today - timedelta(days=n)).isoformat() for n in range(1, 36)}
        self.status = {"status": "ready" if days else "no_daily_data",
                       "statistic_id": self.statistic_id, "days_imported": len(days),
                       "latest_day": max(days) if days else None,
                       "missing_recent_days": len(recent_expected - days.keys()),
                       "backfill_start": self.cache["start"], "backfill_cursor": self.cache["cursor"]}


def usage_pattern(days: dict[str, float], today: date | None = None) -> dict:
    """Flag three consecutive high days against the preceding 28-day mean."""
    today = today or datetime.now(WATER_TIME_ZONE).date()
    dates = [(today - timedelta(days=n)).isoformat() for n in range(1, 32)]
    if any(day not in days for day in dates):
        return {"status": "insufficient_data"}
    baseline = sum(days[d] for d in dates[3:]) / 28
    threshold = max(0.5, baseline * 2)
    elevated = all(days[d] > threshold for d in dates[:3])
    return {"status": "elevated" if elevated else "normal",
            "baseline_m3": round(baseline, 3), "threshold_m3": round(threshold, 3),
            "comparison_days": 3, "baseline_days": 28,
            "latest_day": dates[0]}

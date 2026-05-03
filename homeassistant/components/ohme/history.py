"""Helpers for syncing finalized Ohme energy history into recorder statistics."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, cast

from ohme import OhmeApiClient, SummaryGranularity

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import (
    CONF_BACKFILL_DAYS,
    DEFAULT_BACKFILL_DAYS,
    DEFAULT_RECENT_SYNC_DAYS,
    DOMAIN,
)

if TYPE_CHECKING:
    from .coordinator import OhmeConfigEntry

_LOGGER = logging.getLogger(__name__)

FULL_HISTORY_START = datetime(2000, 1, 1, tzinfo=dt_util.UTC)
HOUR_FETCH_WINDOW = timedelta(days=7)
MONTH_PREFILTER_WINDOW = timedelta(days=3660)
CLEAR_STATISTICS_TIMEOUT = 180
STORE_VERSION = 1

MONTH_GRANULARITY: Any = getattr(SummaryGranularity, "MONTH", "MONTH")


@dataclass(slots=True)
class ImportedStatisticsState:
    """Summarize imported statistics for the Ohme energy statistic."""

    last_start: datetime | None = None
    last_sum_kwh: float | None = None

    @property
    def exists(self) -> bool:
        """Return True if recorder already has statistics for this sensor."""
        return self.last_sum_kwh is not None


def get_backfill_days(config_entry: OhmeConfigEntry) -> int:
    """Return the configured Ohme backfill lookback in days."""
    return max(
        0,
        int(config_entry.options.get(CONF_BACKFILL_DAYS, DEFAULT_BACKFILL_DAYS)),
    )


def backfill_window_covers(
    previous_backfill_days: int, current_backfill_days: int
) -> bool:
    """Return True if the previous backfill window fully covers the current one."""
    if previous_backfill_days == 0:
        return True
    if current_backfill_days == 0:
        return False
    return previous_backfill_days >= current_backfill_days


def floor_to_hour(timestamp: datetime) -> datetime:
    """Return a UTC datetime rounded down to the hour."""
    return dt_util.as_utc(timestamp).replace(minute=0, second=0, microsecond=0)


def history_window_end(now: datetime | None = None) -> datetime:
    """Return the next UTC hour boundary for history queries."""
    timestamp = dt_util.as_utc(now or dt_util.utcnow())
    return floor_to_hour(timestamp) + timedelta(hours=1)


def history_window_start(
    config_entry: OhmeConfigEntry, now: datetime | None = None
) -> datetime:
    """Return the configured history window start for this config entry."""
    window_end = history_window_end(now)
    backfill_days = get_backfill_days(config_entry)
    if backfill_days == 0:
        return FULL_HISTORY_START
    return max(FULL_HISTORY_START, window_end - timedelta(days=backfill_days))


def repair_window_start(
    config_entry: OhmeConfigEntry, now: datetime | None = None
) -> datetime:
    """Return the bounded repair window start for daily/fallback syncs."""
    window_end = history_window_end(now)
    return max(
        history_window_start(config_entry, now),
        window_end - timedelta(days=DEFAULT_RECENT_SYNC_DAYS),
    )


def extract_total_wh(summary_data: Mapping[str, Any] | None) -> int | None:
    """Extract the cumulative charged-energy total from summary payload."""
    total_stats = (summary_data or {}).get("totalStats") or {}
    total_wh = total_stats.get("energyChargedTotalWh")
    if total_wh is None:
        return None
    return int(total_wh)


def extract_total_kwh(summary_data: Mapping[str, Any] | None) -> float | None:
    """Extract the cumulative charged-energy total in kWh."""
    total_wh = extract_total_wh(summary_data)
    if total_wh is None:
        return None
    return total_wh / 1000


def _coerce_row_start(value: Any) -> datetime:
    """Normalize recorder statistic row start values to UTC datetimes."""
    if isinstance(value, datetime):
        return dt_util.as_utc(value)
    return dt_util.utc_from_timestamp(float(value))


def _to_ms(timestamp: datetime) -> int:
    """Convert a timezone-aware datetime to milliseconds since epoch."""
    return int(timestamp.timestamp() * 1000)


def _store(hass: HomeAssistant, config_entry: OhmeConfigEntry) -> Store[dict[str, Any]]:
    """Return the storage helper for persisted sync state."""
    return Store(
        hass,
        STORE_VERSION,
        f"{DOMAIN}.{config_entry.entry_id}.history_sync",
    )


async def async_load_sync_state(
    hass: HomeAssistant, config_entry: OhmeConfigEntry
) -> dict[str, Any] | None:
    """Load persisted sync state for this config entry."""
    return await _store(hass, config_entry).async_load()


async def async_save_sync_state(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
) -> None:
    """Persist the last successfully applied history-sync settings."""
    await _store(hass, config_entry).async_save(
        {CONF_BACKFILL_DAYS: get_backfill_days(config_entry)}
    )


async def async_remove_sync_state(
    hass: HomeAssistant, config_entry: OhmeConfigEntry
) -> None:
    """Remove persisted sync state for this config entry."""
    await _store(hass, config_entry).async_remove()


def statistic_id_from_serial(serial: str) -> str:
    """Return the external statistic id used for Ohme charged energy history."""
    return f"{DOMAIN}:total_charged_energy_{serial.lower().replace('-', '_')}"


def statistic_id(client: OhmeApiClient) -> str:
    """Return the external statistic id used for Ohme charged energy history."""
    return statistic_id_from_serial(client.serial)


def statistics_metadata(client: OhmeApiClient) -> StatisticMetaData:
    """Build recorder statistics metadata for Ohme charged energy."""
    device_name = client.device_info.get("name", client.serial)
    return StatisticMetaData(
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name=f"{device_name} total charged energy",
        source=DOMAIN,
        statistic_id=statistic_id(client),
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )


async def async_fetch_active_month_ranges(
    client: OhmeApiClient, start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    """Fetch month windows which contain non-zero charged energy."""
    if start >= end:
        return []

    active_ranges: list[tuple[datetime, datetime]] = []
    pending_range: tuple[datetime, datetime] | None = None
    chunk_start = start

    while chunk_start < end:
        chunk_end = min(end, chunk_start + MONTH_PREFILTER_WINDOW)
        summary = await client.async_get_charge_summary(
            start_ts=_to_ms(chunk_start),
            end_ts=_to_ms(chunk_end),
            granularity=MONTH_GRANULARITY,
        )

        for stat in cast(list[Mapping[str, Any]], summary.get("stats") or []):
            if (stat.get("energyChargedTotalWh") or 0) <= 0:
                continue

            start_ms = cast(int | None, stat.get("startTime"))
            end_ms = cast(int | None, stat.get("endTime"))
            if start_ms is None or end_ms is None:
                continue

            month_start = max(start, dt_util.utc_from_timestamp(start_ms / 1000))
            month_end = min(end, dt_util.utc_from_timestamp(end_ms / 1000))
            if month_start >= month_end:
                continue

            if pending_range is None:
                pending_range = (month_start, month_end)
                continue

            pending_start, pending_end = pending_range
            if month_start <= pending_end:
                pending_range = (pending_start, max(pending_end, month_end))
                continue

            active_ranges.append(pending_range)
            pending_range = (month_start, month_end)

        chunk_start = chunk_end

    if pending_range is not None:
        active_ranges.append(pending_range)

    _LOGGER.debug(
        "Ohme month prefilter found %s active range(s) between %s and %s",
        len(active_ranges),
        start,
        end,
    )
    return active_ranges


async def async_fetch_hourly_energy_points_for_ranges(
    client: OhmeApiClient, ranges: list[tuple[datetime, datetime]]
) -> list[tuple[datetime, float]]:
    """Fetch hourly charged-energy points for the provided ranges."""
    hourly_points: dict[datetime, float] = {}

    for range_start, range_end in ranges:
        chunk_start = range_start
        while chunk_start < range_end:
            chunk_end = min(range_end, chunk_start + HOUR_FETCH_WINDOW)
            summary = await client.async_get_charge_summary(
                start_ts=_to_ms(chunk_start),
                end_ts=_to_ms(chunk_end),
                granularity=SummaryGranularity.HOUR,
            )

            for stat in cast(list[Mapping[str, Any]], summary.get("stats") or []):
                start_ms = cast(int | None, stat.get("startTime"))
                if start_ms is None:
                    continue

                bucket_start = dt_util.utc_from_timestamp(start_ms / 1000)
                if bucket_start < chunk_start or bucket_start >= chunk_end:
                    continue

                hourly_points[bucket_start] = (
                    stat.get("energyChargedTotalWh") or 0
                ) / 1000

            chunk_start = chunk_end

    return sorted(hourly_points.items())


async def async_fetch_hourly_energy_points_direct(
    client: OhmeApiClient, start: datetime, end: datetime
) -> list[tuple[datetime, float]]:
    """Fetch hourly charged-energy points directly for a bounded window."""
    return await async_fetch_hourly_energy_points_for_ranges(client, [(start, end)])


async def async_fetch_hourly_energy_points(
    client: OhmeApiClient,
    start: datetime,
    end: datetime,
    *,
    use_month_prefilter: bool | None = None,
) -> list[tuple[datetime, float]]:
    """Fetch hourly charged-energy points using the most appropriate strategy."""
    if start >= end:
        return []

    if use_month_prefilter is None:
        use_month_prefilter = end - start > HOUR_FETCH_WINDOW

    if not use_month_prefilter:
        return await async_fetch_hourly_energy_points_direct(client, start, end)

    active_ranges = await async_fetch_active_month_ranges(client, start, end)
    return await async_fetch_hourly_energy_points_for_ranges(client, active_ranges)


def build_cumulative_statistics(
    hourly_points: list[tuple[datetime, float]],
    *,
    window_start: datetime,
    base_sum_kwh: float = 0.0,
) -> list[StatisticData]:
    """Build cumulative recorder rows from hourly energy deltas."""
    statistics: list[StatisticData] = []
    current_sum = base_sum_kwh

    if not hourly_points or hourly_points[0][0] > window_start:
        statistics.append(
            StatisticData(start=window_start, state=current_sum, sum=current_sum)
        )

    for bucket_start, bucket_kwh in hourly_points:
        current_sum = round(current_sum + bucket_kwh, 6)
        statistics.append(
            StatisticData(start=bucket_start, state=current_sum, sum=current_sum)
        )

    return statistics


async def async_get_total_before_window(
    client: OhmeApiClient, window_start: datetime
) -> float:
    """Return the all-time charged-energy total before the requested window."""
    if window_start <= FULL_HISTORY_START:
        return 0.0

    summary = await client.async_get_charge_summary(
        start_ts=_to_ms(FULL_HISTORY_START),
        end_ts=_to_ms(window_start),
        granularity=SummaryGranularity.DAY,
    )
    return extract_total_kwh(cast(Mapping[str, Any], summary)) or 0.0


async def async_get_imported_statistics_state(
    hass: HomeAssistant, stat_id: str
) -> ImportedStatisticsState:
    """Return the current recorder statistics bounds for this sensor."""
    stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics,
        hass,
        1,
        stat_id,
        False,
        {"sum"},
    )
    rows = stats.get(stat_id, [])
    if not rows:
        return ImportedStatisticsState()

    last_sum = rows[-1]["sum"]
    return ImportedStatisticsState(
        last_start=_coerce_row_start(rows[-1]["start"]),
        last_sum_kwh=float(last_sum) if last_sum is not None else None,
    )


async def async_get_sum_before(
    hass: HomeAssistant, stat_id: str, end: datetime
) -> float:
    """Return the cumulative sum immediately before the provided window end."""
    if end <= FULL_HISTORY_START:
        return 0.0

    stats = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        FULL_HISTORY_START,
        end,
        {stat_id},
        "hour",
        None,
        {"sum"},
    )
    rows = stats.get(stat_id, [])
    if not rows:
        return 0.0
    last_sum = rows[-1]["sum"]
    return float(last_sum) if last_sum is not None else 0.0


async def async_clear_statistics(hass: HomeAssistant, stat_id: str) -> None:
    """Clear statistics for the provided statistic id and wait for completion."""
    done_event = asyncio.Event()

    def _done() -> None:
        hass.loop.call_soon_threadsafe(done_event.set)

    get_instance(hass).async_clear_statistics([stat_id], on_done=_done)
    async with asyncio.timeout(CLEAR_STATISTICS_TIMEOUT):
        await done_event.wait()


async def async_remove_energy_history(
    hass: HomeAssistant, config_entry: OhmeConfigEntry
) -> None:
    """Remove imported Ohme energy history and persisted sync state."""
    runtime_data = getattr(config_entry, "runtime_data", None)
    serial = (
        runtime_data.charge_session_coordinator.client.serial
        if runtime_data is not None
        else config_entry.unique_id
    )
    if serial is not None:
        _LOGGER.debug(
            "Removing imported Ohme energy history for serial %s", serial
        )
        await async_clear_statistics(hass, statistic_id_from_serial(serial))
    await async_remove_sync_state(hass, config_entry)


async def async_sync_energy_history_window(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    *,
    window_start: datetime,
    reason: str,
    full_rebuild: bool = False,
    base_sum_kwh_override: float | None = None,
) -> dict[str, Any]:
    """Sync Ohme finalized hourly history into recorder statistics."""
    client = config_entry.runtime_data.charge_session_coordinator.client
    stat_id = statistic_id(client)
    metadata = statistics_metadata(client)
    desired_window_start = history_window_start(config_entry)
    query_end = history_window_end()
    normalized_start = max(desired_window_start, floor_to_hour(window_start))

    if normalized_start >= query_end:
        return {
            "action": "noop",
            "reason": "empty_window",
            "statistic_id": stat_id,
            "window_start": normalized_start.isoformat(),
            "window_end": query_end.isoformat(),
        }

    _LOGGER.debug(
        "Starting Ohme energy history sync (%s): full_rebuild=%s window_start=%s query_end=%s desired_window_start=%s",
        reason,
        full_rebuild,
        normalized_start,
        query_end,
        desired_window_start,
    )

    existing = await async_get_imported_statistics_state(hass, stat_id)
    if full_rebuild:
        if base_sum_kwh_override is not None:
            base_sum_kwh = base_sum_kwh_override
            _LOGGER.debug(
                "Using existing imported Ohme baseline before %s: %s kWh",
                normalized_start,
                base_sum_kwh,
            )
        else:
            base_sum_kwh = await async_get_total_before_window(client, normalized_start)
    else:
        if not existing.exists:
            _LOGGER.debug(
                "Ohme history sync (%s) found no imported statistics; falling back to full rebuild",
                reason,
            )
            return await async_full_rebuild_energy_history(
                hass,
                config_entry,
                reason=f"{reason}_fallback_full_rebuild",
            )
        base_sum_kwh = await async_get_sum_before(hass, stat_id, normalized_start)

    use_month_prefilter = query_end - normalized_start > HOUR_FETCH_WINDOW
    hourly_points = await async_fetch_hourly_energy_points(
        client,
        normalized_start,
        query_end,
        use_month_prefilter=use_month_prefilter,
    )
    statistics = build_cumulative_statistics(
        hourly_points,
        window_start=normalized_start,
        base_sum_kwh=base_sum_kwh,
    )
    if full_rebuild and existing.exists:
        await async_clear_statistics(hass, stat_id)
    async_add_external_statistics(hass, metadata, statistics)
    await async_save_sync_state(hass, config_entry)

    _LOGGER.debug(
        "Ohme energy history sync complete (%s): full_rebuild=%s, points=%s, start=%s, end=%s, prefilter=%s",
        reason,
        full_rebuild,
        len(statistics),
        normalized_start,
        query_end,
        use_month_prefilter,
    )

    return {
        "action": "full_rebuild" if full_rebuild else "window_sync",
        "reason": reason,
        "statistic_id": stat_id,
        "hours_imported": len(statistics),
        "window_start": normalized_start.isoformat(),
        "window_end": query_end.isoformat(),
        "backfill_days": get_backfill_days(config_entry),
        "used_month_prefilter": use_month_prefilter,
    }


async def async_full_rebuild_energy_history(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    *,
    reason: str,
    base_sum_kwh_override: float | None = None,
) -> dict[str, Any]:
    """Perform a full history rebuild for the configured backfill window."""
    return await async_sync_energy_history_window(
        hass,
        config_entry,
        window_start=history_window_start(config_entry),
        full_rebuild=True,
        reason=reason,
        base_sum_kwh_override=base_sum_kwh_override,
    )


async def async_recover_energy_history(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    *,
    reason: str,
) -> dict[str, Any]:
    """Recover any missing history from the last imported hour onward."""
    client = config_entry.runtime_data.charge_session_coordinator.client
    stat_id = statistic_id(client)
    imported_state = await async_get_imported_statistics_state(hass, stat_id)
    if not imported_state.exists or imported_state.last_start is None:
        return await async_full_rebuild_energy_history(
            hass,
            config_entry,
            reason=f"{reason}_fallback_full_rebuild",
        )

    return await async_sync_energy_history_window(
        hass,
        config_entry,
        window_start=max(
            history_window_start(config_entry),
            imported_state.last_start - timedelta(hours=1),
        ),
        reason=reason,
    )


async def async_sync_session_energy_history(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    *,
    session_start: datetime | None,
    reason: str,
) -> dict[str, Any]:
    """Re-import the finalized session window using the active session anchor."""
    if session_start is None:
        return await async_sync_repair_energy_history(
            hass,
            config_entry,
            reason=f"{reason}_fallback_repair",
        )

    return await async_sync_energy_history_window(
        hass,
        config_entry,
        window_start=session_start,
        reason=reason,
    )


async def async_sync_repair_energy_history(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    *,
    reason: str,
) -> dict[str, Any]:
    """Re-import a bounded repair window to catch late provider updates."""
    return await async_sync_energy_history_window(
        hass,
        config_entry,
        window_start=repair_window_start(config_entry),
        reason=reason,
    )


async def async_ensure_energy_history(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
) -> dict[str, Any]:
    """Ensure recorder statistics exist and match the current history settings."""
    client = config_entry.runtime_data.charge_session_coordinator.client
    stat_id = statistic_id(client)
    imported_state = await async_get_imported_statistics_state(hass, stat_id)
    sync_state = await async_load_sync_state(hass, config_entry)
    backfill_days = get_backfill_days(config_entry)

    if not imported_state.exists:
        _LOGGER.debug(
            "Ohme energy history missing for entry %s; starting full rebuild",
            config_entry.entry_id,
        )
        return await async_full_rebuild_energy_history(
            hass,
            config_entry,
            reason="missing_statistics",
        )

    if sync_state is None:
        _LOGGER.debug(
            "Ohme energy history has no persisted sync state for entry %s; saving current settings",
            config_entry.entry_id,
        )
        await async_save_sync_state(hass, config_entry)
    elif sync_state.get(CONF_BACKFILL_DAYS) != backfill_days:
        previous_backfill_days = max(
            0, int(sync_state.get(CONF_BACKFILL_DAYS, DEFAULT_BACKFILL_DAYS))
        )
        base_sum_kwh_override: float | None = None
        if backfill_window_covers(previous_backfill_days, backfill_days):
            base_sum_kwh_override = await async_get_sum_before(
                hass,
                stat_id,
                history_window_start(config_entry),
            )
            _LOGGER.debug(
                "Ohme backfill shrink for entry %s can reuse recorder baseline: previous=%s current=%s baseline=%s kWh",
                config_entry.entry_id,
                previous_backfill_days,
                backfill_days,
                base_sum_kwh_override,
            )
        _LOGGER.debug(
            "Ohme backfill_days changed for entry %s: previous=%s current=%s; rebuilding history",
            config_entry.entry_id,
            previous_backfill_days,
            backfill_days,
        )
        return await async_full_rebuild_energy_history(
            hass,
            config_entry,
            reason="backfill_days_changed",
            base_sum_kwh_override=base_sum_kwh_override,
        )

    _LOGGER.debug(
        "Ohme energy history present for entry %s; running startup recovery",
        config_entry.entry_id,
    )
    return await async_recover_energy_history(
        hass,
        config_entry,
        reason="startup_recovery",
    )

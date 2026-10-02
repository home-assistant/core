"""Import correctly timestamped hourly statistics for the Sense trend sensors."""

from datetime import datetime, timedelta
import logging

from sense_energy import ASyncSenseable, Scale

from homeassistant.components.recorder import DOMAIN as RECORDER_DOMAIN, get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    statistics_during_period,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import (
    CONSUMPTION_ID,
    DOMAIN,
    FROM_GRID_ID,
    PRODUCTION_ID,
    TO_GRID_ID,
    TREND_UPDATE_MINUTES,
    TRENDS_SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)
WINDOW_HOURS = 6
MAX_CACHED_HOURS = 24
ANCHOR_LOOKBACKS = (
    timedelta(hours=MAX_CACHED_HOURS),
    timedelta(days=7),
    timedelta(days=90),
)

STATISTIC_VARIANTS = (CONSUMPTION_ID, PRODUCTION_ID, FROM_GRID_ID, TO_GRID_ID)


def _as_utc_hour(value: datetime) -> datetime:
    """Return the start of the UTC hour containing value."""
    return dt_util.as_utc(value).replace(minute=0, second=0, microsecond=0)


def _metadata(entity_id: str) -> StatisticMetaData:
    """Return the statistics metadata for one taken-over entity."""
    return StatisticMetaData(
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name=None,
        source=RECORDER_DOMAIN,
        statistic_id=entity_id,
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )


class SenseStatistics:
    """Rewrite the recent hourly statistics of the Sense trend sensors.

    Sense only finalizes a clock hour once it has ended, so the trend sensors' live
    state always lags an hour and the recorder books it into the wrong bucket. This
    fetches each completed hour explicitly and imports it against the entities' own
    statistic IDs, which preserves their history and any Energy dashboard setup.
    """

    def __init__(self, hass: HomeAssistant, gateway: ASyncSenseable) -> None:
        """Initialize."""
        self._hass = hass
        self._gateway = gateway
        self._hourly: dict[datetime, dict[str, float]] = {}
        self._provisional: tuple[datetime, dict[str, float]] | None = None

    async def async_import(self) -> None:
        """Fetch any hours still missing from the window and rewrite it."""
        now = dt_util.utcnow()
        window_end = _as_utc_hour(now)
        window = [
            window_end - timedelta(hours=offset)
            for offset in range(WINDOW_HOURS, 0, -1)
        ]

        for hour in window:
            if hour not in self._hourly and (values := await self._async_fetch(hour)):
                self._hourly[hour] = values
        cutoff = window[-1] - timedelta(hours=MAX_CACHED_HOURS)
        for hour in [hour for hour in self._hourly if hour < cutoff]:
            del self._hourly[hour]

        await self._async_import_hours(window, self._hourly)
        if now.minute >= TREND_UPDATE_MINUTES[-1]:
            if values := await self._async_fetch(window_end):
                self._provisional = (window_end, values)

    async def async_import_provisional(self) -> None:
        """Import the newest completed hour from its last in-progress reading.

        The recorder compiles that hour from its own running sum, which does not
        follow ours, so until the first refresh of the hour imports the final value
        the Energy dashboard shows a wrong bar for it. This makes no API calls.
        """
        if self._provisional is None:
            return
        hour, values = self._provisional
        if hour != _as_utc_hour(dt_util.utcnow()) - timedelta(hours=1):
            return
        await self._async_import_hours([hour], {hour: values})

    async def _async_fetch(self, hour: datetime) -> dict[str, float] | None:
        """Fetch the energy of one hour, or None if Sense answered for another."""
        await self._gateway.get_trend_data(Scale.HOUR, hour)
        start = self._gateway.trend_start(Scale.HOUR)
        if start is None or _as_utc_hour(start) != hour:
            _LOGGER.debug("Sense returned %s when asked for hour %s", start, hour)
            return None
        return {
            variant: self._gateway.get_stat(Scale.HOUR, variant)
            for variant in STATISTIC_VARIANTS
        }

    async def _async_import_hours(
        self, hours: list[datetime], hourly: dict[datetime, dict[str, float]]
    ) -> None:
        """Import the given consecutive hours for every target."""
        if not (targets := self._targets()):
            return

        recorder = get_instance(self._hass)
        anchors, existing = await recorder.async_add_executor_job(
            self._read_statistics,
            set(targets),
            hours[0],
            hours[-1] + timedelta(hours=1),
        )
        self._write(targets, hours, hourly, anchors, existing)

    def _targets(self) -> dict[str, tuple[Scale, str]]:
        """Return the entity ID of each taken-over sensor and what it reports.

        Resolved through the registry so renamed entities are followed. A sensor that
        is not registered yet is picked up on a later run; a disabled one is skipped.
        """
        registry = er.async_get(self._hass)
        monitor_id = self._gateway.sense_monitor_id
        targets: dict[str, tuple[Scale, str]] = {}
        for scale, scale_name in TRENDS_SENSOR_TYPES.items():
            for variant in STATISTIC_VARIANTS:
                unique_id = f"{monitor_id}-{scale_name.lower()}-{variant}"
                entity_id = registry.async_get_entity_id(
                    SENSOR_DOMAIN, DOMAIN, unique_id
                )
                if entity_id is None:
                    continue
                entry = registry.async_get(entity_id)
                if entry is None or entry.disabled:
                    continue
                targets[entity_id] = (scale, variant)
        return targets

    def _read_statistics(
        self, entity_ids: set[str], window_start: datetime, window_end: datetime
    ) -> tuple[dict[str, float], dict[str, dict[float, float | None]]]:
        """Return each entity's anchor sum and the states already in the window."""
        anchors: dict[str, float] = {}
        remaining = set(entity_ids)
        for lookback in ANCHOR_LOOKBACKS:
            rows = statistics_during_period(
                self._hass,
                window_start - lookback,
                window_start,
                remaining,
                "hour",
                None,
                {"sum"},
            )
            for entity_id, entity_rows in rows.items():
                if (last := entity_rows[-1].get("sum")) is not None:
                    anchors[entity_id] = last
            remaining -= set(anchors)
            if not remaining:
                break

        window_rows = statistics_during_period(
            self._hass,
            window_start,
            window_end,
            entity_ids,
            "hour",
            None,
            {"state"},
        )
        existing = {
            entity_id: {row["start"]: row.get("state") for row in entity_rows}
            for entity_id, entity_rows in window_rows.items()
        }
        return anchors, existing

    def _write(
        self,
        targets: dict[str, tuple[Scale, str]],
        window: list[datetime],
        hourly: dict[datetime, dict[str, float]],
        anchors: dict[str, float],
        existing: dict[str, dict[float, float | None]],
    ) -> None:
        """Import the window for every target, each continuing its own sum."""
        newest = window[-1]
        for entity_id, (scale, variant) in targets.items():
            running = anchors.get(entity_id, 0.0)
            states = existing.get(entity_id, {})
            rows: list[StatisticData] = []
            for hour in window:
                if (values := hourly.get(hour)) is None:
                    break
                running += values[variant]
                row = StatisticData(start=hour, sum=running)
                state = (
                    self._gateway.get_stat(scale, variant)
                    if hour == newest
                    else states.get(hour.timestamp())
                )
                if state is not None:
                    row["state"] = state
                rows.append(row)
            if rows:
                async_import_statistics(self._hass, _metadata(entity_id), rows)

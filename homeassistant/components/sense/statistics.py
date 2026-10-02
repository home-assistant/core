"""Import correctly timestamped hourly statistics for the Sense trend sensors."""

from datetime import datetime, timedelta
import logging

from sense_energy import ASyncSenseable, Scale

from homeassistant.components.recorder import (
    DOMAIN as RECORDER_DOMAIN,
    get_instance,
    is_entity_recorded,
)
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_last_statistics,
    get_metadata,
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

STATISTIC_VARIANTS = (CONSUMPTION_ID, PRODUCTION_ID, FROM_GRID_ID, TO_GRID_ID)


def _as_utc_hour(value: datetime) -> datetime:
    """Return the start of the UTC hour containing value."""
    return dt_util.as_utc(value).replace(minute=0, second=0, microsecond=0)


def _metadata(entity_id: str, unit: str) -> StatisticMetaData:
    """Return the statistics metadata for one taken-over entity."""
    return StatisticMetaData(
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name=None,
        source=RECORDER_DOMAIN,
        statistic_id=entity_id,
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement=unit,
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
        if now.minute < TREND_UPDATE_MINUTES[0]:
            self._hourly.pop(window[-1], None)
        if now.minute >= TREND_UPDATE_MINUTES[-1] and (
            values := await self._async_fetch(window_end)
        ):
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
        units, anchors, existing = await recorder.async_add_executor_job(
            self._read_statistics,
            set(targets),
            hours[0],
            hours[-1] + timedelta(hours=1),
        )
        self._write(targets, hours, hourly, units, anchors, existing)

    def _targets(self) -> dict[str, tuple[Scale, str]]:
        """Return the entity ID of each taken-over sensor and what it reports.

        Resolved through the registry so renamed entities are followed. A sensor that
        is not registered yet is picked up on a later run; one that is disabled or
        excluded from the recorder is skipped.
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
                if not is_entity_recorded(self._hass, entity_id):
                    continue
                targets[entity_id] = (scale, variant)
        return targets

    def _read_statistics(
        self, entity_ids: set[str], window_start: datetime, window_end: datetime
    ) -> tuple[dict[str, str], dict[str, float], dict[str, dict[float, float | None]]]:
        """Return each entity's unit, anchor sum and the states already in the window."""
        units: dict[str, str] = {}
        for entity_id, (_, metadata) in get_metadata(
            self._hass, statistic_ids=entity_ids
        ).items():
            unit = metadata["unit_of_measurement"]
            if unit is not None and unit in EnergyConverter.VALID_UNITS:
                units[entity_id] = unit

        anchors: dict[str, float] = {}
        window_start_ts = window_start.timestamp()
        number_of_stats = round((window_end - window_start) / timedelta(hours=1)) + 1
        for entity_id in units:
            rows = get_last_statistics(
                self._hass, number_of_stats, entity_id, False, {"sum"}
            )
            previous = {
                row["start"]: total
                for row in rows.get(entity_id, [])
                if row["start"] < window_start_ts
                and (total := row.get("sum")) is not None
            }
            if previous:
                anchors[entity_id] = previous[max(previous)]

        existing: dict[str, dict[float, float | None]] = {}
        for unit in set(units.values()):
            window_rows = statistics_during_period(
                self._hass,
                window_start,
                window_end,
                {
                    entity_id
                    for entity_id, entity_unit in units.items()
                    if entity_unit == unit
                },
                "hour",
                {EnergyConverter.UNIT_CLASS: unit},
                {"state"},
            )
            for entity_id, entity_rows in window_rows.items():
                existing[entity_id] = {
                    row["start"]: row.get("state") for row in entity_rows
                }
        return units, anchors, existing

    def _write(
        self,
        targets: dict[str, tuple[Scale, str]],
        window: list[datetime],
        hourly: dict[datetime, dict[str, float]],
        units: dict[str, str],
        anchors: dict[str, float],
        existing: dict[str, dict[float, float | None]],
    ) -> None:
        """Import the window for every target, each continuing its own sum."""
        newest = window[-1]
        for entity_id, (scale, variant) in targets.items():
            # After a reset the period-to-date value no longer describes the hour.
            period_start = self._gateway.trend_start(scale)
            period_reset = (
                period_start is not None and dt_util.as_utc(period_start) > newest
            )
            if not (states := existing.get(entity_id)):
                continue
            compiled_until = max(states)
            unit = units[entity_id]
            convert = EnergyConverter.converter_factory(
                UnitOfEnergy.KILO_WATT_HOUR, unit
            )
            running = anchors.get(entity_id, 0.0)
            rows: list[StatisticData] = []
            for hour in window:
                if hour.timestamp() > compiled_until:
                    break
                if (values := hourly.get(hour)) is None:
                    break
                running += convert(values[variant])
                row = StatisticData(start=hour, sum=running)
                state = (
                    convert(self._gateway.get_stat(scale, variant))
                    if hour == newest and not period_reset
                    else states.get(hour.timestamp())
                )
                if state is not None:
                    row["state"] = state
                rows.append(row)
            if rows:
                async_import_statistics(self._hass, _metadata(entity_id, unit), rows)

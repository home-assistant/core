"""Import MS120 local history into Home Assistant statistics."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
import logging
from statistics import fmean
from typing import TYPE_CHECKING

from meross_ble import HistorySample, MerossBLEError, MerossModel

from homeassistant.components.recorder.models import StatisticData, StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_HUMI_HISTORY_LAST_TS,
    CONF_HUMI_HISTORY_NEXT_IDX,
    CONF_TEMP_HISTORY_LAST_TS,
    CONF_TEMP_HISTORY_NEXT_IDX,
)

if TYPE_CHECKING:
    from .coordinator import MerossBLEDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

RECORDER_DOMAIN = "recorder"
STAT_PERIOD = timedelta(hours=1)


def _period_floor(ts: datetime, period: timedelta) -> datetime:
    """Align timestamp down to statistics period boundary (UTC)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    seconds = int(period.total_seconds())
    epoch = int(ts.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % seconds), tz=UTC)


def _period_statistics(samples: list[HistorySample]) -> list[StatisticData]:
    """Bucket samples into hourly mean/min/max for recorder import."""
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for sample in samples:
        period = _period_floor(sample.timestamp, STAT_PERIOD)
        buckets[period].append(sample.value)
    return [
        StatisticData(
            start=period,
            mean=round(fmean(values), 2),
            min=round(min(values), 2),
            max=round(max(values), 2),
        )
        for period, values in sorted(buckets.items())
    ]


def _entity_id(hass: HomeAssistant, platform_domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("sensor", platform_domain, unique_id)


def _parse_cutoff(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _filter_newer(
    samples: list[HistorySample], cutoff: datetime | None
) -> list[HistorySample]:
    if cutoff is None:
        return samples
    return [s for s in samples if s.timestamp > cutoff]


def _import_series(
    hass: HomeAssistant,
    *,
    address: str,
    entity_id: str | None,
    samples: list[HistorySample],
    all_fetched: list[HistorySample],
    new_data: dict,
    next_key: str,
    last_ts_key: str,
    unit_of_measurement: str,
    unit_class: str | None,
    label: str,
) -> bool:
    """Import samples and update progress keys. Return True if entry data changed."""
    if not samples:
        _LOGGER.debug("%s: no new %s history to import", address, label)
        return False

    if not entity_id:
        _LOGGER.warning(
            "%s: %s history fetched (%s samples) but entity not registered yet",
            address,
            label,
            len(samples),
        )
        return False

    statistics = _period_statistics(samples)
    if not statistics:
        _LOGGER.debug("%s: no hourly %s buckets to import", address, label)
        return False

    try:
        async_import_statistics(
            hass,
            {
                "has_sum": False,
                "mean_type": StatisticMeanType.ARITHMETIC,
                "name": None,
                "source": RECORDER_DOMAIN,
                "statistic_id": entity_id,
                "unit_class": unit_class,
                "unit_of_measurement": unit_of_measurement,
            },
            statistics,
        )
    except HomeAssistantError as err:
        _LOGGER.error(
            "%s: failed to import %s history into %s (%s firmware samples, "
            "%s hourly buckets): %s",
            address,
            label,
            entity_id,
            len(samples),
            len(statistics),
            err,
        )
        return False

    if all_fetched:
        new_data[next_key] = max(s.index for s in all_fetched) + 1
    new_data[last_ts_key] = max(s.timestamp for s in samples).isoformat()
    _LOGGER.debug(
        "%s: imported %s %s history samples as %s hourly buckets into %s",
        address,
        len(samples),
        label,
        len(statistics),
        entity_id,
    )
    return True


async def async_sync_ms120_history(
    hass: HomeAssistant, coordinator: MerossBLEDataUpdateCoordinator
) -> None:
    """Pull MS120 history over GATT and import into HA statistics."""
    if coordinator.model is not MerossModel.MS120:
        return

    entry = coordinator.config_entry
    platform_domain = entry.domain
    force_full = bool(coordinator.history_force_full_resync)
    coordinator.history_force_full_resync = False

    temp_next = 0 if force_full else int(entry.data.get(CONF_TEMP_HISTORY_NEXT_IDX, 0))
    humi_next = 0 if force_full else int(entry.data.get(CONF_HUMI_HISTORY_NEXT_IDX, 0))
    temp_cutoff = _parse_cutoff(entry.data.get(CONF_TEMP_HISTORY_LAST_TS))
    humi_cutoff = _parse_cutoff(entry.data.get(CONF_HUMI_HISTORY_LAST_TS))

    try:
        temp_all = await coordinator.device.fetch_temperature_history(temp_next)
        humi_all = await coordinator.device.fetch_humidity_history(humi_next)
    except MerossBLEError as err:
        _LOGGER.warning(
            "%s: MS120 history sync failed: %s", coordinator.ble_device.address, err
        )
        return

    if force_full:
        temp_samples = _filter_newer(temp_all, temp_cutoff)
        humi_samples = _filter_newer(humi_all, humi_cutoff)
    else:
        temp_samples = temp_all
        humi_samples = humi_all

    new_data = dict(entry.data)
    address = coordinator.ble_device.address
    updated = False

    updated |= _import_series(
        hass,
        address=address,
        entity_id=_entity_id(
            hass, platform_domain, f"{coordinator.base_unique_id}-temperature"
        ),
        samples=temp_samples,
        all_fetched=temp_all,
        new_data=new_data,
        next_key=CONF_TEMP_HISTORY_NEXT_IDX,
        last_ts_key=CONF_TEMP_HISTORY_LAST_TS,
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_class=TemperatureConverter.UNIT_CLASS,
        label="temperature",
    )
    updated |= _import_series(
        hass,
        address=address,
        entity_id=_entity_id(
            hass, platform_domain, f"{coordinator.base_unique_id}-humidity"
        ),
        samples=humi_samples,
        all_fetched=humi_all,
        new_data=new_data,
        next_key=CONF_HUMI_HISTORY_NEXT_IDX,
        last_ts_key=CONF_HUMI_HISTORY_LAST_TS,
        unit_of_measurement=PERCENTAGE,
        unit_class=None,
        label="humidity",
    )

    if updated:
        hass.config_entries.async_update_entry(entry, data=new_data)

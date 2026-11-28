"""Actions for Withings."""

from collections import defaultdict
from datetime import datetime, timedelta
from enum import StrEnum
from functools import partial
from statistics import fmean
from typing import TYPE_CHECKING

from aiohttp import ClientError
from aiowithings import MeasurementType, aggregate_measurements
from aiowithings.exceptions import WithingsError
from aiowithings.models import MeasurementGroupCategory
import probatio

from homeassistant.components.recorder import DOMAIN as RECORDER_DOMAIN, get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.service import (
    async_get_config_entry,
    async_register_admin_service,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import MassConverter

from .const import DOMAIN

if TYPE_CHECKING:
    from . import WithingsConfigEntry


class WithingsService(StrEnum):
    """Withings actions."""

    BACKFILL_WEIGHT_STATISTICS = "backfill_weight_statistics"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Withings actions."""
    async_register_admin_service(
        hass,
        DOMAIN,
        WithingsService.BACKFILL_WEIGHT_STATISTICS,
        async_backfill_weight_statistics,
        schema=probatio.Schema({probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string}),
    )


async def async_backfill_weight_statistics(call: ServiceCall) -> None:
    """Import missing historical hours for the existing weight sensor."""
    hass = call.hass
    entry: WithingsConfigEntry = async_get_config_entry(
        hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    if RECORDER_DOMAIN not in hass.config.components:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="recorder_required"
        )
    entity_id = _async_get_weight_entity_id(hass, entry)
    recorder = get_instance(hass)
    if (
        entity_id is None
        or hass.states.get(entity_id) is None
        or (
            recorder.entity_filter is not None and not recorder.entity_filter(entity_id)
        )
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="weight_sensor_required"
        )

    # Leave the current and previous hour to Recorder's live compilation.
    end = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=1
    )
    start = dt_util.utc_from_timestamp(0)
    try:
        measurements = await entry.runtime_data.client.get_measurement_in_period(
            start, end, [MeasurementType.WEIGHT]
        )
    except (WithingsError, ClientError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="weight_history_failed"
        ) from err
    _async_ensure_weight_entity_id(hass, entry, entity_id)

    hourly: dict[datetime, list[float]] = defaultdict(list)
    for group in measurements:
        if group.category is not MeasurementGroupCategory.REAL:
            continue
        hour = dt_util.as_utc(group.taken_at).replace(minute=0, second=0, microsecond=0)
        if not start <= hour < end:
            continue
        if (
            weight := aggregate_measurements([group]).get(
                (MeasurementType.WEIGHT, None)
            )
        ) is not None:
            hourly[hour].append(weight)
    if not hourly:
        return

    metadata_by_id = await recorder.async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={entity_id})
    )
    metadata: StatisticMetaData
    if entity_id in metadata_by_id:
        metadata = metadata_by_id[entity_id][1]
    else:
        # Match the unit Recorder will use when it compiles the sensor's states.
        state = hass.states.get(entity_id)
        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=False,
            name=None,
            source=RECORDER_DOMAIN,
            statistic_id=entity_id,
            unit_class=MassConverter.UNIT_CLASS,
            unit_of_measurement=(
                state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
            ),
        )
    unit = metadata["unit_of_measurement"]
    if unit is None or unit not in MassConverter.VALID_UNITS:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_weight_unit"
        )
    existing = await recorder.async_add_executor_job(
        statistics_during_period,
        hass,
        min(hourly),
        end,
        {entity_id},
        "hour",
        None,
        set(),
    )
    existing_hours = {row["start"] for row in existing.get(entity_id, [])}
    statistics: list[StatisticData] = []
    for hour, weights in sorted(hourly.items()):
        if hour.timestamp() in existing_hours:
            continue
        converted = [
            MassConverter.convert(weight, UnitOfMass.KILOGRAMS, unit)
            for weight in weights
        ]
        statistics.append(
            StatisticData(
                start=hour,
                mean=fmean(converted),
                min=min(converted),
                max=max(converted),
            )
        )
    if statistics:
        _async_ensure_weight_entity_id(hass, entry, entity_id)
        async_import_statistics(hass, metadata, statistics)


@callback
def _async_get_weight_entity_id(
    hass: HomeAssistant, entry: WithingsConfigEntry
) -> str | None:
    """Return the current entity ID of the account's weight sensor."""
    return er.async_get(hass).async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"withings_{entry.unique_id}_weight_kg"
    )


@callback
def _async_ensure_weight_entity_id(
    hass: HomeAssistant, entry: WithingsConfigEntry, entity_id: str
) -> None:
    """Stop if the weight sensor was renamed while the action was waiting."""
    if _async_get_weight_entity_id(hass, entry) != entity_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="weight_sensor_changed"
        )

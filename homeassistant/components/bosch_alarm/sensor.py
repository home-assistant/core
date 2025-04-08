"""Support for Bosch Alarm Panel History as a sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bosch_alarm_mode2 import Panel
from bosch_alarm_mode2.const import ALARM_MEMORY_PRIORITIES
from bosch_alarm_mode2.panel import Area

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .entity import BoschAlarmAreaEntity

priority_types = {
    "burglary": {
        "alarm": ALARM_MEMORY_PRIORITIES.BURGLARY_ALARM,
        "supervisory": ALARM_MEMORY_PRIORITIES.BURGLARY_SUPERVISORY,
        "trouble": ALARM_MEMORY_PRIORITIES.BURGLARY_TROUBLE,
    },
    "gas": {
        "alarm": ALARM_MEMORY_PRIORITIES.GAS_ALARM,
        "supervisory": ALARM_MEMORY_PRIORITIES.GAS_SUPERVISORY,
        "trouble": ALARM_MEMORY_PRIORITIES.GAS_TROUBLE,
    },
    "fire": {
        "alarm": ALARM_MEMORY_PRIORITIES.FIRE_ALARM,
        "supervisory": ALARM_MEMORY_PRIORITIES.FIRE_SUPERVISORY,
        "trouble": ALARM_MEMORY_PRIORITIES.FIRE_TROUBLE,
    },
    "personal_emergency": {"alarm": ALARM_MEMORY_PRIORITIES.PERSONAL_EMERGENCY},
}


@dataclass(kw_only=True, frozen=True)
class BoschAlarmSensorEntityDescription(SensorEntityDescription):
    """Describes Bosch Alarm sensor entity."""

    value_fn: Callable[[Area], str]


SENSOR_TYPES: tuple[BoschAlarmSensorEntityDescription, ...] = (
    BoschAlarmSensorEntityDescription(
        key="alarms_burglary",
        translation_key="alarms_burglary",
        value_fn=lambda area: next(
            (
                key
                for key, priority in priority_types["burglary"].items()
                if priority in area.alarms_ids
            ),
            "no_alarms",
        ),
    ),
    BoschAlarmSensorEntityDescription(
        key="alarms_gas",
        translation_key="alarms_gas",
        value_fn=lambda area: next(
            (
                key
                for key, priority in priority_types["gas"].items()
                if priority in area.alarms_ids
            ),
            "no_alarms",
        ),
    ),
    BoschAlarmSensorEntityDescription(
        key="alarms_fire",
        translation_key="alarms_fire",
        value_fn=lambda area: next(
            (
                key
                for key, priority in priority_types["fire"].items()
                if priority in area.alarms_ids
            ),
            "no_alarms",
        ),
    ),
    BoschAlarmSensorEntityDescription(
        key="alarms_personal_emergency",
        translation_key="alarms_personal_emergency",
        value_fn=lambda area: next(
            (
                key
                for key, priority in priority_types["personal_emergency"].items()
                if priority in area.alarms_ids
            ),
            "no_alarms",
        ),
    ),
    BoschAlarmSensorEntityDescription(
        key="faulting_points",
        translation_key="faulting_points",
        value_fn=lambda area: str(area.faults),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bosch alarm sensors."""

    panel = config_entry.runtime_data
    unique_id = config_entry.unique_id or config_entry.entry_id
    entities: list[SensorEntity] = []
    for template in SENSOR_TYPES:
        entities.extend(
            BoschAreaSensor(panel, area_id, unique_id, template)
            for area_id in panel.areas
        )

    async_add_entities(entities)


PARALLEL_UPDATES = 0


class BoschAreaSensor(SensorEntity, BoschAlarmAreaEntity):
    """A faults sensor entity for a bosch alarm panel."""

    entity_description: BoschAlarmSensorEntityDescription

    def __init__(
        self,
        panel: Panel,
        area_id: int,
        unique_id: str,
        entity_description: BoschAlarmSensorEntityDescription,
    ) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        super().__init__(panel, area_id, unique_id, entity_description)

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._area)

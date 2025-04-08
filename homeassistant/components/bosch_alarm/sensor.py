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
        ALARM_MEMORY_PRIORITIES.BURGLARY_SUPERVISORY: "supervisory",
        ALARM_MEMORY_PRIORITIES.BURGLARY_TROUBLE: "trouble",
    },
    "gas": {
        ALARM_MEMORY_PRIORITIES.GAS_SUPERVISORY: "supervisory",
        ALARM_MEMORY_PRIORITIES.GAS_TROUBLE: "trouble",
    },
    "fire": {
        ALARM_MEMORY_PRIORITIES.FIRE_SUPERVISORY: "supervisory",
        ALARM_MEMORY_PRIORITIES.FIRE_TROUBLE: "trouble",
    },
}


@dataclass(kw_only=True, frozen=True)
class BoschAlarmSensorEntityDescription(SensorEntityDescription):
    """Describes Bosch Alarm sensor entity."""

    value_fn: Callable[[Area], str | int]
    observe_alarms: bool = False
    observe_ready: bool = False


def priority_value_fn(priority_info: dict[int, str]) -> Callable[[Area], str]:
    """Build a value_fn for a given priority type."""
    return lambda area: next(
        (key for priority, key in priority_info.items() if priority in area.alarms_ids),
        "no_issues",
    )


SENSOR_TYPES: list[BoschAlarmSensorEntityDescription] = [
    BoschAlarmSensorEntityDescription(
        key=f"alarms_{key}",
        translation_key=f"alarms_{key}",
        value_fn=priority_value_fn(priority_type),
        observe_alarms=True,
    )
    for key, priority_type in priority_types.items()
]
SENSOR_TYPES.append(
    BoschAlarmSensorEntityDescription(
        key="faulting_points",
        translation_key="faulting_points",
        value_fn=lambda area: area.faults,
        observe_ready=True,
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
    """An area sensor entity for a bosch alarm panel."""

    entity_description: BoschAlarmSensorEntityDescription

    def __init__(
        self,
        panel: Panel,
        area_id: int,
        unique_id: str,
        entity_description: BoschAlarmSensorEntityDescription,
    ) -> None:
        """Set up an area sensor entity for a bosch alarm panel."""
        super().__init__(
            panel,
            area_id,
            unique_id,
            entity_description.key,
            entity_description.observe_alarms,
            entity_description.observe_ready,
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> str | int:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._area)

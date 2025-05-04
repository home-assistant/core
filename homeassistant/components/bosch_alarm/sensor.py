"""Support for Bosch Alarm Panel History as a sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bosch_alarm_mode2 import Panel
from bosch_alarm_mode2.panel import Area

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .entity import BoschAlarmAreaEntity


@dataclass(kw_only=True, frozen=True)
class BoschAlarmSensorEntityDescription(SensorEntityDescription):
    """Describes Bosch Alarm sensor entity."""

    value_fn: Callable[[Area], int]
    observe_alarms: bool = False
    observe_ready: bool = False
    observe_status: bool = False


SENSOR_TYPES: list[BoschAlarmSensorEntityDescription] = [
    BoschAlarmSensorEntityDescription(
        key="faulting_points",
        translation_key="faulting_points",
        value_fn=lambda area: area.faults,
        observe_ready=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bosch alarm sensors."""

    panel = config_entry.runtime_data
    unique_id = config_entry.unique_id or config_entry.entry_id

    async_add_entities(
        BoschAreaSensor(panel, area_id, unique_id, template)
        for area_id in panel.areas
        for template in SENSOR_TYPES
    )


PARALLEL_UPDATES = 0


class BoschAreaSensor(BoschAlarmAreaEntity, SensorEntity):
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
            entity_description.observe_alarms,
            entity_description.observe_ready,
            entity_description.observe_status,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._area_unique_id}_{entity_description.key}"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._area)

"""Sensors for the Ablago integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from ablago import Zaehlerstand

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AblagoConfigEntry
from .entity import AblagoEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AblagoSensorEntityDescription(SensorEntityDescription):
    """Describes an Ablago sensor."""

    value_fn: Callable[[Zaehlerstand], int | datetime | None]


SENSORS: tuple[AblagoSensorEntityDescription, ...] = (
    AblagoSensorEntityDescription(
        key="new_mail",
        translation_key="new_mail",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.neue_post,
    ),
    AblagoSensorEntityDescription(
        key="to_do",
        translation_key="to_do",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.zu_erledigen,
    ),
    AblagoSensorEntityDescription(
        key="overdue",
        translation_key="overdue",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.ueberfaellig,
    ),
    AblagoSensorEntityDescription(
        key="last_change",
        translation_key="last_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.geaendert,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AblagoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        AblagoSensor(coordinator, description) for description in SENSORS
    )


class AblagoSensor(AblagoEntity, SensorEntity):
    """A counter of one person."""

    entity_description: AblagoSensorEntityDescription

    @property
    @override
    def native_value(self) -> int | datetime | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

"""Support for Twente Milieu sensors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from twentemilieu import WasteType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TwenteMilieuConfigEntry
from .entity import TwenteMilieuEntity


@dataclass(frozen=True, kw_only=True)
class TwenteMilieuSensorDescription(SensorEntityDescription):
    """Describe an Twente Milieu sensor."""

    waste_type: WasteType


SENSORS: tuple[TwenteMilieuSensorDescription, ...] = (
    TwenteMilieuSensorDescription(
        key="tree",
        translation_key="christmas_tree_pickup",
        waste_type=WasteType.TREE,
        device_class=SensorDeviceClass.DATE,
    ),
    TwenteMilieuSensorDescription(
        key="non_recyclable",
        translation_key="non_recyclable_waste_pickup",
        waste_type=WasteType.NON_RECYCLABLE,
        device_class=SensorDeviceClass.DATE,
    ),
    TwenteMilieuSensorDescription(
        key="organic",
        translation_key="organic_waste_pickup",
        waste_type=WasteType.ORGANIC,
        device_class=SensorDeviceClass.DATE,
    ),
    TwenteMilieuSensorDescription(
        key="paper",
        translation_key="paper_waste_pickup",
        waste_type=WasteType.PAPER,
        device_class=SensorDeviceClass.DATE,
    ),
    TwenteMilieuSensorDescription(
        key="packages",
        translation_key="packages_waste_pickup",
        waste_type=WasteType.PACKAGES,
        device_class=SensorDeviceClass.DATE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TwenteMilieuConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Twente Milieu sensor based on a config entry."""
    async_add_entities(
        TwenteMilieuSensor(entry, description) for description in SENSORS
    )


class TwenteMilieuSensor(TwenteMilieuEntity, SensorEntity):
    """Defines a Twente Milieu sensor."""

    entity_description: TwenteMilieuSensorDescription

    def __init__(
        self,
        entry: TwenteMilieuConfigEntry,
        description: TwenteMilieuSensorDescription,
    ) -> None:
        """Initialize the Twente Milieu entity."""
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

    @property
    def native_value(self) -> date | None:
        """Return the state of the sensor."""
        if not (dates := self.coordinator.data[self.entity_description.waste_type]):
            return None
        return dates[0]

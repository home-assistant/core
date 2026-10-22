"""Sensor platform for Karakeep."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiokarakeep import KarakeepStats

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import KarakeepConfigEntry
from .entity import KarakeepEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KarakeepSensorEntityDescription(SensorEntityDescription):
    """Describes a Karakeep sensor."""

    value_fn: Callable[[KarakeepStats], int]


SENSOR_DESCRIPTIONS: tuple[KarakeepSensorEntityDescription, ...] = (
    KarakeepSensorEntityDescription(
        key="bookmarks",
        translation_key="bookmarks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.num_bookmarks,
    ),
    KarakeepSensorEntityDescription(
        key="favorites",
        translation_key="favorites",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.num_favorites,
    ),
    KarakeepSensorEntityDescription(
        key="archived",
        translation_key="archived",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.num_archived,
    ),
    KarakeepSensorEntityDescription(
        key="highlights",
        translation_key="highlights",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.num_highlights,
    ),
    KarakeepSensorEntityDescription(
        key="lists",
        translation_key="lists",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.num_lists,
    ),
    KarakeepSensorEntityDescription(
        key="tags",
        translation_key="tags",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.num_tags,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KarakeepConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Karakeep sensors based on a config entry."""
    async_add_entities(
        KarakeepStatSensor(entry, description) for description in SENSOR_DESCRIPTIONS
    )


class KarakeepStatSensor(KarakeepEntity, SensorEntity):
    """Representation of a Karakeep statistic as a sensor entity."""

    entity_description: KarakeepSensorEntityDescription

    def __init__(
        self,
        entry: KarakeepConfigEntry,
        entity_description: KarakeepSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry.runtime_data)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

"""Sensor platform for Karakeep."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KarakeepConfigEntry
from .entity import KarakeepEntity


@dataclass(frozen=True, kw_only=True)
class KarakeepSensorEntityDescription(SensorEntityDescription):
    """Describes a Karakeep sensor."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[KarakeepSensorEntityDescription, ...] = (
    KarakeepSensorEntityDescription(
        key="bookmarks",
        translation_key="bookmarks",
        icon="mdi:bookmark",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bookmarks",
        value_key="numBookmarks",
    ),
    KarakeepSensorEntityDescription(
        key="favorites",
        translation_key="favorites",
        icon="mdi:star",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="favorites",
        value_key="numFavorites",
    ),
    KarakeepSensorEntityDescription(
        key="archived",
        translation_key="archived",
        icon="mdi:archive",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="items",
        value_key="numArchived",
    ),
    KarakeepSensorEntityDescription(
        key="highlights",
        translation_key="highlights",
        icon="mdi:marker",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="highlights",
        value_key="numHighlights",
    ),
    KarakeepSensorEntityDescription(
        key="lists",
        translation_key="lists",
        icon="mdi:format-list-bulleted",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="lists",
        value_key="numLists",
    ),
    KarakeepSensorEntityDescription(
        key="tags",
        translation_key="tags",
        icon="mdi:tag",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="tags",
        value_key="numTags",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KarakeepConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
        self._attr_unique_id = f"{entry.data[CONF_URL]}_{entity_description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        value: Any = self.coordinator.data.get(self.entity_description.value_key)
        return value if isinstance(value, int) else None

"""BleBox sensor entities."""
from dataclasses import dataclass

from blebox_uniapi.binary_sensor import BinarySensor as BinarySensorFeature

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, create_blebox_entities


@dataclass
class BleboxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Blebox binary sensor entities."""


BINARY_SENSOR_TYPES = (
    BleboxBinarySensorEntityDescription(
        key="moisture",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""

    create_blebox_entities(
        hass,
        config_entry,
        async_add_entities,
        BleBoxBinarySensorEntity,
        "binary_sensors",
    )


class BleBoxBinarySensorEntity(BleBoxEntity, BinarySensorEntity):
    """Representation of a BleBox binary sensor feature."""

    def __init__(self, feature: BinarySensorFeature) -> None:
        """Initialize a BleBox sensor feature."""
        super().__init__(feature)

        for description in BINARY_SENSOR_TYPES:
            if description.key == feature.device_class:
                self.entity_description = description
                break

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self._feature.state

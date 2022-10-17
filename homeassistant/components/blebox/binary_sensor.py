"""BleBox binary sensor entities."""

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

BINARY_SENSOR_TYPES = (
    BinarySensorEntityDescription(
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
        BINARY_SENSOR_TYPES,
    )


class BleBoxBinarySensorEntity(BleBoxEntity, BinarySensorEntity):
    """Representation of a BleBox binary sensor feature."""

    def __init__(
        self, feature: BinarySensorFeature, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize a BleBox binary sensor feature."""
        super().__init__(feature)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self._feature.state

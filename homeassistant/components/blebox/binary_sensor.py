"""BleBox binary sensor entities."""

from blebox_uniapi.binary_sensor import BinarySensor as BinarySensorFeature

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BleBoxConfigEntry
from .entity import BleBoxEntity

BINARY_SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key="moisture",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""
    entities = [
        BleBoxBinarySensorEntity(feature, description)
        for feature in config_entry.runtime_data.features.get("binary_sensors", [])
        for description in BINARY_SENSOR_TYPES
        if description.key == feature.device_class
    ]
    async_add_entities(entities, True)


class BleBoxBinarySensorEntity(BleBoxEntity[BinarySensorFeature], BinarySensorEntity):
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

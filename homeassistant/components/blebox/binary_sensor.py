"""BleBox binary sensor entities."""

from blebox_uniapi.binary_sensor import BinarySensor as BinarySensorFeature
from blebox_uniapi.box import Box

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PRODUCT
from .entity import BleBoxEntity

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

    product: Box = hass.data[DOMAIN][config_entry.entry_id][PRODUCT]
    entities = [
        BleBoxBinarySensorEntity(feature, description)
        for feature in product.features.get("binary_sensors", [])
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

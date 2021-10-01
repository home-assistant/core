"""BleBox sensor entities."""

from homeassistant.components.sensor import SensorEntity

from . import BleBoxEntity, create_blebox_entities
from .const import BLEBOX_TO_HASS_DEVICE_CLASSES, BLEBOX_TO_UNIT_MAP


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a BleBox entry."""

    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxSensorEntity, "sensors"
    )


class BleBoxSensorEntity(BleBoxEntity, SensorEntity):
    """Representation of a BleBox sensor feature."""

    def __init__(self, feature):
        """Initialize a BleBox sensor feature."""
        super().__init__(feature)
        self._attr_native_unit_of_measurement = BLEBOX_TO_UNIT_MAP[feature.unit]
        self._attr_device_class = BLEBOX_TO_HASS_DEVICE_CLASSES[feature.device_class]

    @property
    def native_value(self):
        """Return the state."""
        return self._feature.current

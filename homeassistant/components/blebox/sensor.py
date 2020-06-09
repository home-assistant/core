"""BleBox sensor entities."""

from homeassistant.helpers.entity import Entity

from . import BleBoxEntity, create_blebox_entities
from .const import BLEBOX_DEV_CLASS_MAP, BLEBOX_TO_UNIT_MAP, DOMAIN, PRODUCT


async def async_setup_entry(hass, config_entry, async_add):
    """Set up a BleBox entry."""

    product = hass.data[DOMAIN][config_entry.entry_id][PRODUCT]
    create_blebox_entities(product, async_add, BleBoxSensorEntity, "sensors")
    return True


class BleBoxSensorEntity(BleBoxEntity, Entity):
    """Representation of a BleBox sensor feature."""

    @property
    def state(self):
        """Return the state."""
        return self._feature.current

    @property
    def unit_of_measurement(self):
        """Return the unit."""
        return BLEBOX_TO_UNIT_MAP[self._feature.unit]

    @property
    def device_class(self):
        """Return the device class."""
        return BLEBOX_DEV_CLASS_MAP[self._feature.device_class]

"""BleBox switch implementation."""
from homeassistant.components.switch import SwitchDevice

from . import BleBoxEntity, create_blebox_entities
from .const import BLEBOX_TO_HASS_DEVICE_CLASSES, DOMAIN, PRODUCT


async def async_setup_entry(hass, config_entry, async_add):
    """Set up a BleBox switch entity."""

    product = hass.data[DOMAIN][config_entry.entry_id][PRODUCT]
    create_blebox_entities(product, async_add, BleBoxSwitchEntity, "switches")
    return True


class BleBoxSwitchEntity(BleBoxEntity, SwitchDevice):
    """Representation of a BleBox switch feature."""

    @property
    def device_class(self):
        """Return the device class."""
        return BLEBOX_TO_HASS_DEVICE_CLASSES[self._feature.device_class]

    @property
    def is_on(self):
        """Return whether switch is on."""
        return self._feature.is_on

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        return await self._feature.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        return await self._feature.async_turn_off()

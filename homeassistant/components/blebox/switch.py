"""BleBox switch implementation."""
from homeassistant.components.switch import SwitchDevice

from . import BleBoxEntity, create_blebox_entities
from .const import BLEBOX_TO_HASS_DEVICE_CLASSES


async def async_setup_entry(hass, config_entry, async_add):
    """Set up a BleBox switch entity."""
    create_blebox_entities(
        hass, config_entry, async_add, BleBoxSwitchEntity, "switches"
    )


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

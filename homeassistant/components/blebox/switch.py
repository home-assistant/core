"""BleBox switch implementation."""
from homeassistant.components.switch import DEVICE_CLASS_SWITCH, SwitchDevice

from . import CommonEntity, async_add_blebox


async def async_setup_platform(hass, config, async_add, discovery_info=None):
    """Set up BleBox platform."""
    return await async_add_blebox(
        # TODO: coverage
        BleBoxSwitchEntity,
        "switches",
        hass,
        config,
        async_add,
    )


async def async_setup_entry(hass, config_entry, async_add):
    """Set up a BleBox entry."""
    return await async_add_blebox(
        BleBoxSwitchEntity, "switches", hass, config_entry.data, async_add,
    )


class BleBoxSwitchEntity(CommonEntity, SwitchDevice):
    """Representation of a BleBox switch feature."""

    @property
    def device_class(self):
        """Return the device class."""
        types = {
            "relay": DEVICE_CLASS_SWITCH,
        }
        return types[self._feature.device_class]

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

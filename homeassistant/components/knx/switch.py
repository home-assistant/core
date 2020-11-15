"""Support for KNX/IP switches."""
from xknx.devices import Switch as XknxSwitch

from homeassistant.components.switch import SwitchEntity

from . import DOMAIN
from .knx_entity import KnxEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up switch(es) for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxSwitch):
            entities.append(KNXSwitch(device))
    async_add_entities(entities)


class KNXSwitch(KnxEntity, SwitchEntity):
    """Representation of a KNX switch."""

    def __init__(self, device: XknxSwitch):
        """Initialize of KNX switch."""
        super().__init__(device)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._device.set_on()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._device.set_off()

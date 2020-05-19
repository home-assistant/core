"""Support for HLK-SW16 switches."""
from homeassistant.components.switch import ToggleEntity
from homeassistant.const import CONF_HOST, CONF_PORT

from . import DATA_DEVICE_REGISTER, SW16Device


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HLK-SW16 switches."""


def devices_from_entities(hass, entry):
    """Parse configuration and add HLK-SW16 switch devices."""
    address = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
    device_client = hass.data[DATA_DEVICE_REGISTER][address]
    devices = []
    for i in range(16):
        device_port = f"{i:01x}"
        device = SW16Switch(device_port, address, device_client)
        devices.append(device)
    return devices


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the HLK-SW16 platform."""
    async_add_entities(devices_from_entities(hass, entry))


class SW16Switch(SW16Device, ToggleEntity):
    """Representation of a HLK-SW16 switch."""

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.turn_on(self._device_port)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._device_port)

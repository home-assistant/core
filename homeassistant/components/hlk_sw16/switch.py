"""Support for HLK-SW16 switches."""
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_DEVICE_REGISTER, SW16Device
from .const import DOMAIN

PARALLEL_UPDATES = 0


def devices_from_entities(hass, entry):
    """Parse configuration and add HLK-SW16 switch devices."""
    device_client = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE_REGISTER]
    devices = []
    for i in range(16):
        device_port = f"{i:01x}"
        device = SW16Switch(device_port, entry.entry_id, device_client)
        devices.append(device)
    return devices


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the HLK-SW16 platform."""
    async_add_entities(devices_from_entities(hass, entry))


class SW16Switch(SW16Device, SwitchEntity):
    """Representation of a HLK-SW16 switch."""

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._client.turn_on(self._device_port)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._client.turn_off(self._device_port)

"""Support for HLK-SW16 switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HlkConfigEntry
from .entity import SW16Entity

PARALLEL_UPDATES = 0


def devices_from_entities(entry: HlkConfigEntry) -> list[SW16Switch]:
    """Parse configuration and add HLK-SW16 switch devices."""
    device_client = entry.runtime_data
    devices = []
    for i in range(16):
        device_port = f"{i:01x}"
        device = SW16Switch(device_port, entry.entry_id, device_client)
        devices.append(device)
    return devices


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HlkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HLK-SW16 platform."""
    async_add_entities(devices_from_entities(entry))


class SW16Switch(SW16Entity, SwitchEntity):
    """Representation of a HLK-SW16 switch."""

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._client.turn_on(self._device_port)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._client.turn_off(self._device_port)

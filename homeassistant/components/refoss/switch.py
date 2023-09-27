"""Switch for Refoss."""

from __future__ import annotations

from typing import Any

from refoss_ha.controller.toggle import ToggleXMix

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantRefossData
from .const import DOMAIN
from .device import RefossEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    hass_data: HomeAssistantRefossData = hass.data[DOMAIN][entry.entry_id]
    device = hass_data.base_device

    new_entities = []
    if not isinstance(device, ToggleXMix):
        return

    for channel in device.channels:
        w = RefossSwitchEntity(device=device, channel=channel)
        new_entities.append(w)
    async_add_entities(new_entities, True)


class RefossSwitchEntity(RefossEntity, SwitchEntity):
    """Entity that controls switch based refoss device."""

    device: ToggleXMix

    def __init__(self, device: ToggleXMix, channel: int) -> None:
        """Construct."""
        super().__init__(device=device, channel=channel)
        self._channel_id = channel

    @property
    def is_on(self) -> bool | None:
        """is_on."""
        return self.device.is_on(channel=self._channel_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """async_turn_on."""
        await self.device.async_turn_on(self._channel_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """async_turn_off."""
        await self.device.async_turn_off(self._channel_id)
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """async_toggle."""
        await self.device.async_toggle(channel=self._channel_id)
        self.async_write_ha_state()

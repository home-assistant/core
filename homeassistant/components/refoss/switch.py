"""Switch for Refoss."""

from __future__ import annotations

from typing import Any

from refoss_ha.controller.toggle import ToggleXMix

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantRefossData
from .const import DOMAIN, REFOSS_DISCOVERY_NEW
from .device import RefossEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    hass_data: HomeAssistantRefossData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def entity_add_callback(device_ids: list[str]) -> None:
        """entity_add_callback."""
        new_entities = []
        for uuid in device_ids:
            device = hass_data.device_manager.base_device_map[uuid]
            if device is None:
                continue
            if not isinstance(device, ToggleXMix):
                continue

            for channel in device.channels:
                w = RefossSwitchEntity(device=device, channel=channel)
                new_entities.append(w)
        async_add_entities(new_entities, True)

    entity_add_callback([*hass_data.device_manager.base_device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, REFOSS_DISCOVERY_NEW, entity_add_callback)
    )


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

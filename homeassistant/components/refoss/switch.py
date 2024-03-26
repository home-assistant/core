"""Switch for Refoss."""

from __future__ import annotations

from typing import Any

from refoss_ha.controller.toggle import ToggleXMix

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATORS, DISPATCH_DEVICE_DISCOVERED, DOMAIN
from .entity import RefossEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Refoss device from a config entry."""

    @callback
    def init_device(coordinator):
        """Register the device."""
        device = coordinator.device
        if not isinstance(device, ToggleXMix):
            return

        new_entities = []
        for channel in device.channels:
            entity = RefossSwitch(coordinator=coordinator, channel=channel)
            new_entities.append(entity)

        async_add_entities(new_entities)

    for coordinator in hass.data[DOMAIN][COORDINATORS]:
        init_device(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class RefossSwitch(RefossEntity, SwitchEntity):
    """Refoss Switch Device."""

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.coordinator.device.is_on(channel=self.channel_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.device.async_turn_on(self.channel_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.device.async_turn_off(self.channel_id)
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        await self.coordinator.device.async_toggle(channel=self.channel_id)
        self.async_write_ha_state()

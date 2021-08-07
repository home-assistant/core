"""Support for Bond generic devices."""
from __future__ import annotations

from typing import Any

from bond_api import Action, BPUPSubscriptions, DeviceType

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BPUP_SUBS, DOMAIN, HUB
from .entity import BondEntity
from .utils import BondHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond generic devices."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: BondHub = data[HUB]
    bpup_subs: BPUPSubscriptions = data[BPUP_SUBS]

    switches: list[Entity] = [
        BondSwitch(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_generic(device.type)
    ]

    async_add_entities(switches, True)


class BondSwitch(BondEntity, SwitchEntity):
    """Representation of a Bond generic device."""

    def _apply_state(self, state: dict) -> None:
        self._attr_is_on = state.get("power") == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._hub.bond.action(self._device.device_id, Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._hub.bond.action(self._device.device_id, Action.turn_off())

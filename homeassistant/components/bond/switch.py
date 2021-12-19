"""Support for Bond generic devices."""
from __future__ import annotations

from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from bond_api import Action, BPUPSubscriptions, DeviceType
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_POWER_STATE,
    BPUP_SUBS,
    DOMAIN,
    HUB,
    SERVICE_SET_POWER_TRACKED_STATE,
)
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
    platform = entity_platform.async_get_current_platform()

    switches: list[Entity] = [
        BondSwitch(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_generic(device.type)
    ]

    platform.async_register_entity_service(
        SERVICE_SET_POWER_TRACKED_STATE,
        {vol.Required(ATTR_POWER_STATE): cv.boolean},
        "async_set_power_belief",
    )

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

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set switch power belief."""
        try:
            await self._hub.bond.action(
                self._device.device_id, Action.set_power_state_belief(power_state)
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                f"The bond API returned an error calling set_power_state_belief for {self.entity_id}.  Code: {ex.code}  Message: {ex.message}"
            ) from ex

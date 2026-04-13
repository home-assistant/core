"""Support for Bond generic devices."""

from __future__ import annotations

from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from bond_async import Action, DeviceType

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BondConfigEntry
from .entity import BondEntity
from .utils import BondGroup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bond generic devices."""
    data = entry.runtime_data

    devices = data.hub.devices + data.hub.groups
    async_add_entities(
        BondSwitch(data, device)
        for device in devices
        if DeviceType.is_generic(device.type)
    )


class BondSwitch(BondEntity, SwitchEntity):
    """Representation of a Bond generic device."""

    def _apply_state(self) -> None:
        power = self._device.state.get("power")
        if isinstance(self._device, BondGroup):
            self._attr_is_on = None if power is None else power == 1
        else:
            self._attr_is_on = power == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._async_action(Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._async_action(Action.turn_off())

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set switch power belief."""
        self._async_ensure_device_only(Action.SET_STATE_BELIEF)
        try:
            await self._async_action(Action.set_power_state_belief(power_state))
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_power_state_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex

"""Support for deCONZ switches."""

from __future__ import annotations

from typing import Any

from pydeconz.models.event import EventType
from pydeconz.models.light.light import Light

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import POWER_PLUGS
from .entity import DeconzDevice
from .hub import DeconzHub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for deCONZ component.

    Switches are based on the same device class as lights in deCONZ.
    """
    hub = DeconzHub.get_hub(hass, config_entry)
    hub.entities[SWITCH_DOMAIN] = set()

    @callback
    def async_add_switch(_: EventType, switch_id: str) -> None:
        """Add switch from deCONZ."""
        switch = hub.api.lights.lights[switch_id]
        if switch.type not in POWER_PLUGS:
            return
        async_add_entities([DeconzPowerPlug(switch, hub)])

    hub.register_platform_add_device_callback(
        async_add_switch,
        hub.api.lights.lights,
    )


class DeconzPowerPlug(DeconzDevice[Light], SwitchEntity):
    """Representation of a deCONZ power plug."""

    TYPE = SWITCH_DOMAIN

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.hub.api.lights.lights.set_state(
            id=self._device.resource_id,
            on=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.hub.api.lights.lights.set_state(
            id=self._device.resource_id,
            on=False,
        )

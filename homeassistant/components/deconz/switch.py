"""Support for deCONZ switches."""

from __future__ import annotations

from typing import Any

from pydeconz.models.light.light import Light

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import POWER_PLUGS
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for deCONZ component.

    Switches are based on the same device class as lights in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_switch(lights: list[Light] | None = None) -> None:
        """Add switch from deCONZ."""
        entities = []

        if lights is None:
            lights = list(gateway.api.lights.lights.values())

        for light in lights:

            if (
                light.type in POWER_PLUGS
                and light.unique_id not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzPowerPlug(light, gateway))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_light,
            async_add_switch,
        )
    )

    async_add_switch()


class DeconzPowerPlug(DeconzDevice, SwitchEntity):
    """Representation of a deCONZ power plug."""

    TYPE = DOMAIN
    _device: Light

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._device.set_state(on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._device.set_state(on=False)

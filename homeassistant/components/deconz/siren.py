"""Support for deCONZ siren."""
from __future__ import annotations

from typing import Any

from pydeconz.models.event import EventType
from pydeconz.models.light.siren import Siren

from homeassistant.components.siren import (
    ATTR_DURATION,
    DOMAIN,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sirens for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_light(_: EventType, light_id: str) -> None:
        """Add siren from deCONZ."""
        light = gateway.api.lights.sirens[light_id]
        async_add_entities([DeconzSiren(light, gateway)])

    config_entry.async_on_unload(
        gateway.api.lights.sirens.subscribe(
            gateway.evaluate_add_device(async_add_light),
            EventType.ADDED,
        )
    )
    for light_id in gateway.api.lights.sirens:
        async_add_light(EventType.ADDED, light_id)


class DeconzSiren(DeconzDevice, SirenEntity):
    """Representation of a deCONZ siren."""

    TYPE = DOMAIN
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.DURATION
    )
    _device: Siren

    @property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on siren."""
        data = {}
        if (duration := kwargs.get(ATTR_DURATION)) is not None:
            data["duration"] = duration * 10
        await self._device.turn_on(**data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off siren."""
        await self._device.turn_off()

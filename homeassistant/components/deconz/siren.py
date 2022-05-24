"""Support for deCONZ siren."""
from __future__ import annotations

from typing import Any

from pydeconz.models.light.siren import Siren

from homeassistant.components.siren import (
    ATTR_DURATION,
    DOMAIN,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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
    def async_add_siren(lights: list[Siren] | None = None) -> None:
        """Add siren from deCONZ."""
        entities = []

        if lights is None:
            lights = list(gateway.api.lights.sirens.values())

        for light in lights:

            if (
                isinstance(light, Siren)
                and light.unique_id not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzSiren(light, gateway))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_light,
            async_add_siren,
        )
    )

    async_add_siren()


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

"""Support for deCONZ siren."""

from __future__ import annotations

from collections.abc import ValuesView
from typing import Any

from pydeconz.light import Siren

from homeassistant.components.siren import (
    ATTR_DURATION,
    DOMAIN,
    SUPPORT_DURATION,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SirenEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sirens for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_siren(
        lights: list[Siren] | ValuesView[Siren] = gateway.api.lights.values(),
    ) -> None:
        """Add siren from deCONZ."""
        entities = []

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
    _device: Siren

    def __init__(self, device: Siren, gateway: DeconzGateway) -> None:
        """Set up siren."""
        super().__init__(device, gateway)

        self._attr_supported_features = (
            SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_DURATION
        )

    @property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self._device.is_on  # type: ignore[no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on siren."""
        data = {}
        if (duration := kwargs.get(ATTR_DURATION)) is not None:
            data["duration"] = duration * 10
        await self._device.turn_on(**data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off siren."""
        await self._device.turn_off()

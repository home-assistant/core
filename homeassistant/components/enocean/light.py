"""Support for EnOcean light sources."""

from __future__ import annotations

from typing import Any

from enocean_async import Dim, EntityType, Gateway, Observable, Observation

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import EnOceanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data

    async_add_entities(
        EnOceanLight(eurid, entity.id, gateway)
        for eurid, spec in gateway.device_specs.items()
        for entity in spec.entities
        if entity.entity_type == EntityType.DIMMER
    )


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light (dimmer)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def _update_from_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        if Observable.OUTPUT_VALUE in observation.values:
            pct = observation.values[Observable.OUTPUT_VALUE]
            self._attr_is_on = pct > 0
            # Convert 0–100 % to HA brightness 0–255.
            self._attr_brightness = round(pct * 255 / 100)
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on or dim the light."""
        brightness: int = kwargs.get(ATTR_BRIGHTNESS, 255)
        # Convert HA brightness 0–255 to 0–100 %.
        await self.gateway.send_command(
            self.address,
            Dim(dim_value=brightness * 100 / 255, entity_id=self.entity_key),
        )

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the light."""
        await self.gateway.send_command(
            self.address,
            # Use Dim(0) rather than Switch so the dimmer's ramp mechanism is used.
            Dim(dim_value=0, switch_on=False, entity_id=self.entity_key),
        )

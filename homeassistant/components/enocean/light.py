"""Support for EnOcean light sources."""

from __future__ import annotations

from typing import Any

from enocean_async import (
    EURID,
    Dim,
    EntityType,
    Gateway,
    Observable,
    Observation,
    Switch,
)

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import EnOceanEntity, EnOceanEntityID


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data
    gateway_eurid: EURID = await gateway.eurid

    entities = []
    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type == EntityType.DIMMER:
                entity_id = EnOceanEntityID(device_address=eurid, unique_id=entity.id)
                entities.append(EnOceanLight(entity_id, gateway, gateway_eurid))

    async_add_entities(entities)


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light (dimmer)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
    ) -> None:
        """Initialize the EnOcean light."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            gateway_eurid=gateway_eurid,
        )
        gateway.add_observation_callback(self._on_observation)

    def _on_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        if (
            observation.device != self.enocean_entity_id.device_address
            or observation.entity != self.enocean_entity_id.unique_id
        ):
            return

        if Observable.OUTPUT_VALUE in observation.values:
            pct = observation.values[Observable.OUTPUT_VALUE]
            self._attr_is_on = pct > 0
            # Convert 0–100 % to HA brightness 0–255.
            self._attr_brightness = round(pct * 255 / 100)
            self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on or dim the light."""
        brightness: int = kwargs.get(ATTR_BRIGHTNESS, 255)
        # Convert HA brightness 0–255 to 0–100 %.
        dim_value = round(brightness * 100 / 255)
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            Dim(dim_value=dim_value, entity_id=self.enocean_entity_id.unique_id),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            Switch(switch_on=False, entity_id=self.enocean_entity_id.unique_id),
        )

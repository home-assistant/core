"""Support for EnOcean switches."""

from typing import Any

from enocean_async import EntityType, Gateway, Observable, Observation, SetSwitchOutput

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
        EnOceanSwitch(eurid, entity.id, gateway)
        for eurid, spec in gateway.device_specs.items()
        for entity in spec.entities
        if entity.entity_type == EntityType.SWITCH
    )


class EnOceanSwitch(EnOceanEntity, SwitchEntity):
    """Representation of an EnOcean switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def _on_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        if observation.device != self.address or observation.entity != self.entity_key:
            return

        if Observable.SWITCH_STATE in observation.values:
            self._attr_is_on = bool(observation.values[Observable.SWITCH_STATE])
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.gateway.send_command(
            self.address,
            SetSwitchOutput(output_value=100, entity_id=self.entity_key),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.gateway.send_command(
            self.address,
            SetSwitchOutput(output_value=0, entity_id=self.entity_key),
        )

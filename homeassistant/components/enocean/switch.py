"""Support for EnOcean switches."""

from typing import Any

from enocean_async import (
    EURID,
    EntityType,
    Gateway,
    Observable,
    Observation,
    SetSwitchOutput,
)

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
            if entity.entity_type == EntityType.SWITCH:
                entity_id = EnOceanEntityID(device_address=eurid, unique_id=entity.id)
                entities.append(EnOceanSwitch(entity_id, gateway, gateway_eurid))

    async_add_entities(entities)


class EnOceanSwitch(EnOceanEntity, SwitchEntity):
    """Representation of an EnOcean switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
    ) -> None:
        """Initialize the EnOcean switch."""
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

        if Observable.SWITCH_STATE in observation.values:
            self._attr_is_on = bool(observation.values[Observable.SWITCH_STATE])
            self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            SetSwitchOutput(
                output_value=100, entity_id=self.enocean_entity_id.unique_id
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.gateway.send_command(
            self.enocean_entity_id.device_address,
            SetSwitchOutput(output_value=0, entity_id=self.enocean_entity_id.unique_id),
        )

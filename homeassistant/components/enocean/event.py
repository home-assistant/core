"""Support for EnOcean button/rocker events."""

from enocean_async import EntityType, Gateway, Observable, Observation

from homeassistant.components.event import EventEntity
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
        EnOceanEvent(eurid, entity.id, gateway)
        for eurid, spec in gateway.device_specs.items()
        for entity in spec.entities
        if entity.entity_type == EntityType.BUTTON
    )


class EnOceanEvent(EnOceanEntity, EventEntity):
    """Representation of an EnOcean button/rocker as an event entity."""

    _attr_event_types = Observable.BUTTON_EVENT.possible_values

    def _on_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        if observation.device != self.address or observation.entity != self.entity_key:
            return

        if Observable.BUTTON_EVENT in observation.values:
            self._trigger_event(observation.values[Observable.BUTTON_EVENT])
            self.async_write_ha_state()

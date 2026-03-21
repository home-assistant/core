"""Support for EnOcean button/rocker events."""

from enocean_async import EURID, EntityType, Gateway, Observable, Observation

from homeassistant.components.event import EventEntity
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
            if entity.entity_type == EntityType.BUTTON:
                entity_id = EnOceanEntityID(device_address=eurid, unique_id=entity.id)
                entities.append(EnOceanEvent(entity_id, gateway, gateway_eurid))

    async_add_entities(entities)


class EnOceanEvent(EnOceanEntity, EventEntity):
    """Representation of an EnOcean button/rocker as an event entity."""

    _attr_event_types = Observable.BUTTON_EVENT.possible_values

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
    ) -> None:
        """Initialize the EnOcean event entity."""
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

        if Observable.BUTTON_EVENT in observation.values:
            event_type = observation.values[Observable.BUTTON_EVENT]
            self._trigger_event(event_type)
            self.schedule_update_ha_state()

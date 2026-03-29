"""Support for EnOcean binary sensors."""

from enocean_async import EntityType, Gateway, Observation
from enocean_async.semantics.value_kind import ValueKind

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import EnOceanEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data

    entities = [
        EnOceanBinarySensor(eurid, entity.id, gateway)
        for eurid, spec in gateway.device_specs.items()
        for entity in spec.entities
        if entity.entity_type == EntityType.BINARY
    ]

    async_add_entities(entities)


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of an EnOcean binary sensor."""

    def _update_from_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        # Pick the first binary-kinded observable value present.
        for obs, value in observation.values.items():
            if obs.kind == ValueKind.BINARY:
                self._attr_is_on = bool(value)
                self.async_write_ha_state()
                return

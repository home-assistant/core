"""Support for EnOcean binary sensors."""

from enocean_async import EURID, EntityType, Gateway, Observation
from enocean_async.semantics.value_kind import ValueKind

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    version_info = await gateway.version_info
    gateway_eurid: EURID = version_info.eurid

    entities = []
    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type == EntityType.BINARY:
                entity_id = EnOceanEntityID(device_address=eurid, unique_id=entity.id)
                entities.append(EnOceanBinarySensor(entity_id, gateway, gateway_eurid))

    async_add_entities(entities)


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of an EnOcean binary sensor."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
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

        # Pick the first binary-kinded observable value present.
        for obs, value in observation.values.items():
            if obs.kind == ValueKind.BINARY:
                self._attr_is_on = bool(value)
                self.schedule_update_ha_state()
                return

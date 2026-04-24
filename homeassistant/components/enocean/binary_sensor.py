"""Support for EnOcean binary sensors."""

from enocean_async import EURID, EntityType, Gateway, Observation
from enocean_async.semantics.value_kind import ValueKind

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import LIB_ENTITY_CATEGORY_MAP, EnOceanEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data
    gateway_eurid = gateway.eurid

    entities: list[EnOceanBinarySensor] = [
        EnOceanBinarySensor(eurid, entity.id, gateway)
        for eurid, spec in gateway.device_specs.items()
        for entity in spec.entities
        if entity.entity_type == EntityType.BINARY
    ]

    if gateway_eurid is not None:
        entities.extend(
            EnOceanBinarySensor(
                gateway_eurid,
                entity.id,
                gateway,
                LIB_ENTITY_CATEGORY_MAP.get(entity.category),
                track_gateway_availability=False,
            )
            for entity in gateway.gateway_entities
            if entity.entity_type == EntityType.BINARY
        )

    async_add_entities(entities)


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of an EnOcean binary sensor."""

    def __init__(
        self,
        address: EURID,
        entity_key: str,
        gateway: Gateway,
        entity_category: EntityCategory | None = None,
        track_gateway_availability: bool = True,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(address, entity_key, gateway)
        self._attr_entity_category = entity_category
        self._track_gateway_availability = track_gateway_availability
        if not track_gateway_availability:
            self._attr_available = True

    def _update_from_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        # Pick the first binary-kinded observable value present.
        for obs, value in observation.values.items():
            if obs.kind == ValueKind.BINARY:
                self._attr_is_on = bool(value)
                self.async_write_ha_state()
                return

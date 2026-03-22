"""Support for EnOcean number entities (integration-local numeric configuration)."""

from __future__ import annotations

from enocean_async import EURID, EntityType, Gateway, NumberRange

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import EnOceanEntity, EnOceanEntityID

_ENTITY_CATEGORY_MAP: dict[str, EntityCategory | None] = {
    "config": EntityCategory.CONFIG,
    "diagnostic": EntityCategory.DIAGNOSTIC,
    "default": None,
}


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
            if entity.entity_type == EntityType.OPTION_NUMBER:
                number_range: NumberRange = entity.option_spec
                entity_id = EnOceanEntityID(device_address=eurid, unique_id=entity.id)
                entities.append(
                    EnOceanNumber(
                        entity_id,
                        gateway,
                        gateway_eurid,
                        number_range,
                        _ENTITY_CATEGORY_MAP.get(entity.category),
                    )
                )

    async_add_entities(entities)


class EnOceanNumber(EnOceanEntity, RestoreNumber):
    """Representation of an EnOcean integration-local numeric config entity."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
        number_range: NumberRange,
        entity_category: EntityCategory | None,
    ) -> None:
        """Initialize the EnOcean number entity."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            gateway_eurid=gateway_eurid,
        )
        self._attr_native_min_value = number_range.min_value
        self._attr_native_max_value = number_range.max_value
        self._attr_native_step = number_range.step
        self._attr_native_unit_of_measurement = number_range.unit
        self._attr_entity_category = entity_category
        self._attr_native_value = number_range.default

    async def async_added_to_hass(self) -> None:
        """Restore last value on restart."""
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_number_data()) is not None:
            self._attr_native_value = last_data.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Store the new value."""
        self._attr_native_value = value
        self.async_write_ha_state()

"""Support for EnOcean select entities (integration-local enum configuration)."""

from __future__ import annotations

from enocean_async import EntityType, EnumOptions, Gateway

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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

    entities = []
    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type == EntityType.OPTION_ENUM:
                enum_options: EnumOptions = entity.option_spec
                entity_id = EnOceanEntityID(device_address=eurid, unique_id=entity.id)
                entities.append(
                    EnOceanSelect(
                        entity_id,
                        gateway,
                        enum_options,
                        _ENTITY_CATEGORY_MAP.get(entity.category),
                    )
                )

    async_add_entities(entities)


class EnOceanSelect(EnOceanEntity, SelectEntity, RestoreEntity):
    """Representation of an EnOcean integration-local enum config entity."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: Gateway,
        enum_options: EnumOptions,
        entity_category: EntityCategory | None,
    ) -> None:
        """Initialize the EnOcean select entity."""
        super().__init__(enocean_entity_id=entity_id, gateway=gateway)
        self._attr_options = list(enum_options.options)
        self._attr_entity_category = entity_category
        self._attr_current_option = enum_options.default

    async def async_added_to_hass(self) -> None:
        """Restore last selected option on restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_options:
                self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()

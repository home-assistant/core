"""The Nibe Heat Pump select."""
from __future__ import annotations

from nibe.coil import Coil

from homeassistant.components.select import ENTITY_ID_FORMAT, SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, CoilEntity, Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Select(coordinator, coil)
        for coil in coordinator.coils
        if coil.is_writable and coil.mappings and not coil.is_boolean
    )


class Select(CoilEntity, SelectEntity):
    """Select entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Coordinator, coil: Coil) -> None:
        """Initialize entity."""
        assert coil.mappings
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)
        self._attr_options = list(coil.mappings.values())
        self._attr_current_option = None

    def _async_read_coil(self, coil: Coil) -> None:
        if not isinstance(coil.value, str):
            self._attr_current_option = None
            return

        self._attr_current_option = coil.value

    async def async_select_option(self, option: str) -> None:
        """Support writing value."""
        await self._async_write_coil(option)

"""The Nibe Heat Pump switch."""

from __future__ import annotations

from typing import Any

from nibe.coil import Coil, CoilData

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import CoilCoordinator
from .entity import CoilEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: CoilCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Switch(coordinator, coil)
        for coil in coordinator.coils
        if coil.is_writable and coil.is_boolean
    )


class Switch(CoilEntity, SwitchEntity):
    """Switch entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CoilCoordinator, coil: Coil) -> None:
        """Initialize entity."""
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)
        self._on_value = coil.get_mapping_for(1)
        self._off_value = coil.get_mapping_for(0)

    def _async_read_coil(self, data: CoilData) -> None:
        self._attr_is_on = data.value == self._on_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_write_coil(self._on_value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_write_coil(self._off_value)

"""The Nibe Heat Pump switch."""
from __future__ import annotations

from typing import Any

from nibe.coil import Coil

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
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
        Switch(coordinator, coil)
        for coil in coordinator.coils
        if coil.is_writable and coil.is_boolean
    )


class Switch(CoilEntity, SwitchEntity):
    """Switch entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Coordinator, coil: Coil) -> None:
        """Initialize entity."""
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)
        self._attr_is_on = None

    def _async_read_coil(self, coil: Coil) -> None:
        self._attr_is_on = coil.value == "ON"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_write_coil("ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_write_coil("OFF")

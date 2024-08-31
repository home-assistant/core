"""The Nibe Heat Pump binary sensors."""
from __future__ import annotations

from nibe.coil import Coil, CoilData

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CoilEntity, Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        BinarySensor(coordinator, coil)
        for coil in coordinator.coils
        if not coil.is_writable and coil.is_boolean
    )


class BinarySensor(CoilEntity, BinarySensorEntity):
    """Binary sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Coordinator, coil: Coil) -> None:
        """Initialize entity."""
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)

    def _async_read_coil(self, data: CoilData) -> None:
        self._attr_is_on = data.value == "ON"

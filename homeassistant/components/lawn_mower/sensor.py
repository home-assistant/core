"""Sensor platform for lawn mower integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize lawn mower config entry."""
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    # TODO Optionally validate config entry options before creating entity
    name = config_entry.title
    unique_id = config_entry.entry_id

    async_add_entities([lawn_mowerSensorEntity(unique_id, name, entity_id)])


class lawn_mowerSensorEntity(SensorEntity):
    """lawn_mower Sensor."""

    def __init__(self, unique_id: str, name: str, wrapped_entity_id: str) -> None:
        """Initialize lawn_mower Sensor."""
        super().__init__()
        self._wrapped_entity_id = wrapped_entity_id
        self._attr_name = name
        self._attr_unique_id = unique_id

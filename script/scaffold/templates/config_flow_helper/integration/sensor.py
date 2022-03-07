"""Sensor platform for NEW_NAME integration."""
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
    """Initialize Light Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    # TODO Optionally validate config entry options before creating entity
    entity_id = config_entry.options[CONF_ENTITY_ID]
    name = config_entry.title
    unique_id = config_entry.entry_id

    async_add_entities([NEW_DOMAINSensorEntity(unique_id, name, entity_id)])


class NEW_DOMAINSensorEntity(SensorEntity):
    """NEW_DOMAIN Sensor."""

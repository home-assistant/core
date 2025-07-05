"""Sensor platform for Victron Energy integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Victron Energy sensors."""
    manager = hass.data[DOMAIN]["manager"]
    manager.set_sensor_add_entities(async_add_entities)

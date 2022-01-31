"""Support for Overkiz climate devices."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.decorator import Registry

from . import HomeAssistantOverkizData
from .const import DOMAIN

CLIMATE_IMPLEMENTATIONS = Registry()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz climate from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]

    entities = [
        CLIMATE_IMPLEMENTATIONS[device.widget](device.device_url, data.coordinator)
        for device in data.platforms[Platform.CLIMATE]
        if device.widget in CLIMATE_IMPLEMENTATIONS
    ]

    async_add_entities(entities)

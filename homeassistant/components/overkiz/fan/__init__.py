"""Support for Overkiz ventilation systems as fans."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .. import OverkizDataConfigEntry
from .ventilation_point import (
    VENTILATION_POINT_DESCRIPTIONS,
    OverkizVentilationPointFan,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz fans from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        OverkizVentilationPointFan(
            device.device_url,
            data.coordinator,
            VENTILATION_POINT_DESCRIPTIONS[device.widget],
        )
        for device in data.platforms[Platform.FAN]
        if device.widget in VENTILATION_POINT_DESCRIPTIONS
    )

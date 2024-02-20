"""Implementation of the Radarr sensor."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    overseer_api_client = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []

    for sensor, sensor_data in SENSOR_TYPES.items():
        sensor_label = sensor
        sensor_type = sensor_data["type"]
        sensor_icon = sensor_data["icon"]
        sensors.append(
            OverseerrSensor(sensor_label, sensor_type, overseer_api_client, sensor_icon)
        )

    async_add_entities(sensors)


class OverseerrSensor(Entity):
    """Representation of an Overseerr sensor."""

    def __init__(self, label, sensor_type, overseerr, icon) -> None:
        """Initialize the sensor."""
        self._label = label
        self._type = sensor_type
        self._overseerr = overseerr
        self._icon = icon
        self._state = None

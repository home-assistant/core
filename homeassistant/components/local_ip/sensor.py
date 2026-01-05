"""Sensor platform for local_ip."""

from homeassistant.components.network import async_get_source_ip
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SENSOR


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    name = entry.data.get(CONF_NAME) or "Local IP"
    async_add_entities([IPSensor(name)], True)


class IPSensor(SensorEntity):
    """A simple sensor."""

    _attr_unique_id = SENSOR
    _attr_translation_key = "local_ip"

    def __init__(self, name: str) -> None:
        """Initialize the sensor."""
        self._attr_name = name

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        self._attr_native_value = await async_get_source_ip(self.hass)

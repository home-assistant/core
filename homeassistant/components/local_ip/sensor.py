"""Sensor platform for local_ip."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import get_local_ip

from .const import DOMAIN, SENSOR


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    name = entry.data.get(CONF_NAME) or DOMAIN
    async_add_entities([IPSensor(name)], True)


class IPSensor(SensorEntity):
    """A simple sensor."""

    _attr_unique_id = SENSOR
    _attr_icon = "mdi:ip"

    def __init__(self, name: str) -> None:
        """Initialize the sensor."""
        self._attr_name = name

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        self._attr_state = get_local_ip()

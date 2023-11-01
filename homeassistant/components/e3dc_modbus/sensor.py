"""Sensors."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# async def async_setup_entry(
#    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
# ) -> None:
#    """Initialisieren."""
#    # hub_name = entry.data[CONF_NAME]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    async_add_entities([DemoSensor(hass.data[DOMAIN][entry.entry_id]["hub"])])


class DemoSensor(SensorEntity):
    """Representation of a Demo Sensor."""

    def __init__(self, hub):
        """Initialize the sensor."""
        self._hub = hub
        self._state = 23.6  # You can set this to any value you want
        self._attr_unique_id = f"{hub.name}_demo_sensor"
        self._attr_name = f"{hub.name}_Demo Sensor"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Disable polling for this sensor since it's value is fixed."""
        return False

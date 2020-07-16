from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_FAHRENHEIT
from .const import DOMAIN

SENSORS = [
    ("water_temperature", "Water Temperature", "temperature", TEMP_FAHRENHEIT),
    ("air_temperature", "Air Temperature", "temperature", TEMP_FAHRENHEIT),
]

SCAN_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    _LOGGER.info("TESTING")

    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        OmnilogicSensor(coordinator, kind, name, device_class, unit)
        for kind, name, device_class, unit in SENSORS
    ]
    async_add_entities(sensors, update_before_add=True)


class OmnilogicSensor(Entity):
    """Defines an Omnilogic sensor entity"""

    def __init__(self, coordinator, kind, name, icon, unit):
        _LOGGER.info("Sensor INIT")
        self._kind = kind
        self._name = name
        self._state = None
        self._unit = unit
        self.coordinator = coordinator

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return True

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        # need a more unique id
        return self._name

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self):
        return self._state

    async def async_update(self):
        """Update Omnilogic entity."""
        await self.coordinator.async_request_refresh()
        if self._kind == "water_temperature":
            self._state = self.coordinator.data["Backyard"]["BOW1"].get("waterTemp")
        elif self._kind == "air_temperature":
            self._state = self.coordinator.data["Backyard"].get("airTemp")

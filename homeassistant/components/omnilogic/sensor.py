from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_FAHRENHEIT, UNIT_PERCENTAGE
from .const import DOMAIN

PERCENT_UNITS = [UNIT_PERCENTAGE, UNIT_PERCENTAGE]
SALT_UNITS = ["g/L", "PPM"]

SENSORS = [
    ("pool_temperature", "Pool Temperature", "temperature", TEMP_FAHRENHEIT),
    ("air_temperature", "Air Temperature", "temperature", TEMP_FAHRENHEIT),
    ("spa_temperature", "Spa Temperature", "temperature", TEMP_FAHRENHEIT),
    ("pool_chlorinator", "Pool Chlorinator", PERCENT_UNITS, "mdi:gauge"),
    ("spa_chlorinator", "Spa Chlorinator", PERCENT_UNITS, "mdi:gauge"),
    ("salt_level", "Salt Level", SALT_UNITS, "mdi:gauge"),
    ("pump_speed", "Pump Speed", PERCENT_UNITS, "mdi:speedometer"),
]

SCAN_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    _LOGGER.info("TESTING")

    coordinator = hass.data[DOMAIN][entry.entry_id]

    for backyard in coordinator.data:
        for bow in backyard["Telemetry"][0]["BOWS"]:
            sensors = [
                OmnilogicSensor(
                    coordinator, kind, name, backyard, bow, device_class, unit
                )
                for kind, name, device_class, unit in SENSORS
            ]
    async_add_entities(sensors, update_before_add=True)


class OmnilogicSensor(Entity):
    """Defines an Omnilogic sensor entity"""

    def __init__(self, coordinator, kind, name, backyard, bow, icon, unit):
        _LOGGER.info("Sensor INIT")
        self._kind = kind
        self._name = name
        self._backyard = backyard
        self._backyardName = backyard["BackyardName"]
        self._state = None
        self._unit = unit
        self._bow = bow
        self.coordinator = coordinator

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return True

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        # need a more unique id
        return self._backyardName + "." + self._name

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def force_update(self):
        """Force update."""
        return True

    @property
    def state(self):

        return self._state

    async def async_update(self):
        """Update Omnilogic entity."""
        await self.coordinator.async_request_refresh()

        if self._kind == "pool_temperature":
            _LOGGER.info("waterTemp")
            _LOGGER.info(self._bow.get("waterTemp"))
            self._state = self._bow.get("waterTemp")
        elif self._kind == "pump_speed":
            _LOGGER.info("filterSpeed")
            _LOGGER.info(self._bow["Filter"].get("filterSpeed"))
            self._state = self._bow["Filter"].get("filterSpeed")
        elif self._kind == "salt_level":
            _LOGGER.info("avgSaltLevel")
            _LOGGER.info(self._bow["Chlorinator"].get("avgSaltLevel"))
            self._state = self._bow["Chlorinator"].get("avgSaltLevel")
        elif self._kind == "pool_chlorinator":
            _LOGGER.info("Timed-Percent")
            _LOGGER.info(self._bow["Chlorinator"].get("Timed-Percent"))
            self._state = self._bow["Chlorinator"].get("Timed-Percent")
        elif self._kind == "air_temperature":
            _LOGGER.info("airTemp")
            _LOGGER.info(self._backyard["Telemetry"][0].get("airTemp"))
            self._state = self._backyard["Telemetry"][0].get("airTemp")

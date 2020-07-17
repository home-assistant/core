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

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""

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
            self._state = self.coordinator.data[0]["Telemetry"][0]["BOWS"][0].get(
                "waterTemp"
            )
        elif self._kind == "pump_speed":
            self._state = self.coordinator.data[0]["Telemetry"][0]["BOWS"][0][
                "Filter"
            ].get("filterSpeed")
        elif self._kind == "salt_level":
            self._state = self.coordinator.data[0]["Telemetry"][0]["BOWS"][0][
                "Chlorinator"
            ].get("avgSaltLevel")
        elif self._kind == "pool_chlorinator":
            self._state = self.coordinator.data[0]["Telemetry"][0]["BOWS"][0][
                "Chlorinator"
            ].get("Timed-Percent")
        elif self._kind == "air_temperature":
            self._state = self.coordinator.data[0]["Telemetry"][0].get("airTemp")

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

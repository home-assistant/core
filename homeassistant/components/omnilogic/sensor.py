"""Support for Omnilogic Sensors."""
from datetime import timedelta
import logging

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from .const import DOMAIN

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = [UNIT_PERCENTAGE, UNIT_PERCENTAGE]
SALT_UNITS = ["g/L", "ppm"]

SENSORS = [
    ("pool_temperature", "Pool Temperature", "temperature", "mdi:thermometer", TEMP_UNITS),
    ("air_temperature", "Air Temperature", "temperature", "mdi:thermometer", TEMP_UNITS),
    ("spa_temperature", "Spa Temperature", "temperature", "mdi:thermometer", TEMP_UNITS),
    ("pool_chlorinator", "Pool Chlorinator", "none", "mdi:gauge", PERCENT_UNITS),
    ("spa_chlorinator", "Spa Chlorinator", "none", "mdi:gauge", PERCENT_UNITS),
    ("salt_level", "Salt Level", "none", "mdi:gauge", SALT_UNITS),
    ("pump_speed", "Pump Speed", "none", "mdi:speedometer", PERCENT_UNITS),
]

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    for backyard in coordinator.data:
        for bow in backyard["BOWS"]:
            sensors = [
                OmnilogicSensor(
                    coordinator, kind, name, backyard, bow, device_class, icon, unit
                )
                for kind, name, device_class, icon, unit in SENSORS
            ]
    async_add_entities(sensors, update_before_add=True)


class OmnilogicSensor(Entity):
    """Defines an Omnilogic sensor entity."""

    def __init__(self, coordinator, kind, name, backyard, bow, device_class, icon, unit):
        """Initialize Entities."""
        sensorname = "omni_" + backyard["BackyardName"].replace(" ", "_") + "_" + bow["Name"].replace(" ", "_") + "_" + kind
        self._kind = kind
        self._name = None
        self.entity_id = ENTITY_ID_FORMAT.format(sensorname)
        self._backyard = backyard
        self._backyard_name = backyard["BackyardName"]
        self._state = None
        self._unit_type = backyard["Unit-of-Measurement"]
        self._device_class = device_class
        self._icon = icon
        self._bow = bow
        self._unit = None
        self.coordinator = coordinator
        self._msp_system_id = backyard["systemId"]
        self._system_id = None
        self._attributes = {}

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
    def device_class(self):
        """Return the device class of the entity."""
        if self._device_class != "none":
            return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the right unit of measure."""
        return self._unit

    @property
    def icon(self):
        """Return the icon for the entity."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        attributes = self._attributes
        attributes["MspSystemId"] = self._msp_system_id
        attributes["SystemId"] = self._system_id
        return attributes

    @property
    def force_update(self):
        """Force update."""
        return True

    @property
    def state(self):
        """Return the state."""
        return self._state

    async def async_update(self):
        """Update Omnilogic entity."""
        await self.coordinator.async_request_refresh()

        if self._kind == "pool_temperature":
            temp_return = float(self.coordinator.data[0]["BOWS"][0].get("waterTemp"))
            unit_of_measurement = TEMP_FAHRENHEIT
            if self.coordinator.data[0]["Unit-of-Measurement"] == "Metric":
                temp_return = round((temp_return - 32) * 5 / 9, 1)
                unit_of_measurement = TEMP_CELSIUS

            self._attributes["hayward_temperature"] = temp_return
            self._attributes["hayward_unit_of_measure"] = unit_of_measurement
            self._state = float(self.coordinator.data[0]["BOWS"][0].get("waterTemp"))
            self._unit = TEMP_FAHRENHEIT
            self._system_id = self.coordinator.data[0]["BOWS"][0].get("systemId")
            self._name = self.coordinator.data[0]["BOWS"][0].get("Name") + " Water Temperature"

        elif self._kind == "pump_speed":
            self._state = self.coordinator.data[0]["BOWS"][0]["Filter"].get(
                "filterSpeed"
            )
            self._unit = "%"
            self._name = self.coordinator.data[0]["BOWS"][0].get("Name") + " " + self.coordinator.data[0]["BOWS"][0]["Filter"].get("Name")
        elif self._kind == "salt_level":
            salt_return = float(self.coordinator.data[0]["BOWS"][0]["Chlorinator"].get("avgSaltLevel"))
            unit_of_measurement = "ppm"

            if self.coordinator.data[0]["Unit-of-Measurement"] == "Metric":
                salt_return = round(salt_return / 1000, 2)
                unit_of_measurement = "g/L"

            self._state = salt_return
            self._unit = unit_of_measurement
            self._system_id = self.coordinator.data[0]["BOWS"][0]["Chlorinator"].get("systemId")
            self._name = self.coordinator.data[0]["BOWS"][0].get("Name") + " " + self.coordinator.data[0]["BOWS"][0]["Chlorinator"].get("Name") + " Salt Level"

        elif self._kind == "pool_chlorinator":
            self._state = self.coordinator.data[0]["BOWS"][0]["Chlorinator"].get(
                "Timed-Percent"
            )
            self._unit = "%"
            self._name = self.coordinator.data[0]["BOWS"][0].get("Name") + " " + self.coordinator.data[0]["BOWS"][0]["Chlorinator"].get("Name") + " Setting"

        elif self._kind == "air_temperature":
            temp_return = float(self.coordinator.data[0].get("airTemp"))
            unit_of_measurement = TEMP_FAHRENHEIT
            if self.coordinator.data[0]["Unit-of-Measurement"] == "Metric":
                temp_return = round((temp_return - 32) * 5 / 9, 1)
                unit_of_measurement = TEMP_CELSIUS

            self._attributes["hayward_temperature"] = temp_return
            self._attributes["hayward_unit_of_measure"] = unit_of_measurement
            self._state = float(self.coordinator.data[0].get("airTemp"))
            self._unit = TEMP_FAHRENHEIT
            self._system_id = self.coordinator.data[0]["BOWS"][0].get("systemId")
            self._name = self.coordinator.data[0]["BOWS"][0].get("Name") + " Air Temperature"

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

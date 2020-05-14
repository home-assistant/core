"""Support for monitoring juicenet/juicepoint/juicebox based EVSE sensors."""
import logging

from homeassistant.const import (
    ENERGY_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_SECONDS,
    VOLT,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, JUICENET_API, JUICENET_COORDINATOR
from .entity import JuiceNetDevice

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "status": ["Charging Status", None],
    "temperature": ["Temperature", TEMP_CELSIUS],
    "voltage": ["Voltage", VOLT],
    "amps": ["Amps", "A"],
    "watts": ["Watts", POWER_WATT],
    "charge_time": ["Charge time", TIME_SECONDS],
    "energy_added": ["Energy added", ENERGY_WATT_HOUR],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the JuiceNet Sensors."""
    entities = []
    juicenet_data = hass.data[DOMAIN][config_entry.entry_id]
    api = juicenet_data[JUICENET_API]
    coordinator = juicenet_data[JUICENET_COORDINATOR]

    for device in api.devices:
        for sensor in SENSOR_TYPES:
            entities.append(JuiceNetSensorDevice(device, sensor, coordinator))
    async_add_entities(entities)


class JuiceNetSensorDevice(JuiceNetDevice, Entity):
    """Implementation of a JuiceNet sensor."""

    def __init__(self, device, sensor_type, coordinator):
        """Initialise the sensor."""
        super().__init__(device, sensor_type, coordinator)
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self.device.name} {self._name}"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        icon = None
        if self.type == "status":
            status = self.device.status
            if status == "standby":
                icon = "mdi:power-plug-off"
            elif status == "plugged":
                icon = "mdi:power-plug"
            elif status == "charging":
                icon = "mdi:battery-positive"
        elif self.type == "temperature":
            icon = "mdi:thermometer"
        elif self.type == "voltage":
            icon = "mdi:flash"
        elif self.type == "amps":
            icon = "mdi:flash"
        elif self.type == "watts":
            icon = "mdi:flash"
        elif self.type == "charge_time":
            icon = "mdi:timer"
        elif self.type == "energy_added":
            icon = "mdi:flash"
        return icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state."""
        state = None
        if self.type == "status":
            state = self.device.status
        elif self.type == "temperature":
            state = self.device.temperature
        elif self.type == "voltage":
            state = self.device.voltage
        elif self.type == "amps":
            state = self.device.amps
        elif self.type == "watts":
            state = self.device.watts
        elif self.type == "charge_time":
            state = self.device.charge_time
        elif self.type == "energy_added":
            state = self.device.energy_added
        else:
            state = "Unknown"
        return state

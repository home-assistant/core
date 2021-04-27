"""Platform for beewi_smartclim integration."""
from beewi_smartclim import BeewiSmartClimPoller  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

# Default values
DEFAULT_NAME = "BeeWi SmartClim"

# Sensor config
SENSOR_TYPES = [
    [DEVICE_CLASS_TEMPERATURE, "Temperature", TEMP_CELSIUS],
    [DEVICE_CLASS_HUMIDITY, "Humidity", PERCENTAGE],
    [DEVICE_CLASS_BATTERY, "Battery", PERCENTAGE],
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the beewi_smartclim platform."""

    mac = config[CONF_MAC]
    prefix = config[CONF_NAME]
    poller = BeewiSmartClimPoller(mac)

    sensors = []

    for sensor_type in SENSOR_TYPES:
        device = sensor_type[0]
        name = sensor_type[1]
        unit = sensor_type[2]
        # `prefix` is the name configured by the user for the sensor, we're appending
        #  the device type at the end of the name (garden -> garden temperature)
        if prefix:
            name = f"{prefix} {name}"

        sensors.append(BeewiSmartclimSensor(poller, name, mac, device, unit))

    add_entities(sensors)


class BeewiSmartclimSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, poller, name, mac, device, unit):
        """Initialize the sensor."""
        self._poller = poller
        self._name = name
        self._mac = mac
        self._device = device
        self._unit = unit
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor. State is returned in Celsius."""
        return self._state

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._device

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._mac}_{self._device}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    def update(self):
        """Fetch new state data from the poller."""
        self._poller.update_sensor()
        self._state = None
        if self._device == DEVICE_CLASS_TEMPERATURE:
            self._state = self._poller.get_temperature()
        if self._device == DEVICE_CLASS_HUMIDITY:
            self._state = self._poller.get_humidity()
        if self._device == DEVICE_CLASS_BATTERY:
            self._state = self._poller.get_battery()

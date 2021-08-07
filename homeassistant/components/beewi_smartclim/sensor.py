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
        self._attr_name = name
        self._device = device
        self._attr_unit_of_measurement = unit
        self._attr_device_class = self._device
        self._attr_unique_id = f"{mac}_{device}"

    def update(self):
        """Fetch new state data from the poller."""
        self._poller.update_sensor()
        self._attr_state = None
        if self._device == DEVICE_CLASS_TEMPERATURE:
            self._attr_state = self._poller.get_temperature()
        if self._device == DEVICE_CLASS_HUMIDITY:
            self._attr_state = self._poller.get_humidity()
        if self._device == DEVICE_CLASS_BATTERY:
            self._attr_state = self._poller.get_battery()

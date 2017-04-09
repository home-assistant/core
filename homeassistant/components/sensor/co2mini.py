"""
Support for the CO2 and temperature sensor of CO2meter's CO2Mini USB indoor air
quality monitor and compatible devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.co2mini/
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICE, CONF_FRIENDLY_NAME, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/jannau/CO2Meter/archive/fea592cfd2b54124e4afdc20320f5c929e1c07d6.zip#CO2Meter==2.0']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
})

DATA_CO2MINI_DEV = 'co2mini_dev'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up CO2 mini Sensor."""
    import CO2Meter

    device = config.get(CONF_DEVICE)
    name = config.get(CONF_FRIENDLY_NAME, device.rsplit('/', 1)[-1])

    sensors = {}
    sensors[CO2Meter.CO2Meter_CO2] = CO2MiniSensor(name + " CO2", "ppm")
    sensors[CO2Meter.CO2Meter_TEMP] = CO2MiniSensor(name + " Temperature", "°C")

    async_add_devices(sensors.values())

    co2mon = CO2MiniMonitor(device, name, sensors)

    if DATA_CO2MINI_DEV not in hass.data:
        hass.data[DATA_CO2MINI_DEV] = {}
    hass.data[DATA_CO2MINI_DEV][device] = co2mon


class CO2MiniMonitor(object):
    """Object for device interaction."""

    def __init__(self, device, name, sensors):
        """Init."""
        import CO2Meter

        self._device = device
        self._name = name
        self._sensors = sensors
        self._co2meter = CO2Meter.CO2Meter(self._device, self.update)

    @callback
    def update(self, sensor, value):
        """Callback to receive sensor readings."""

        if sensor in self._sensors:
            self._sensors[sensor].state = value
            self._sensors[sensor].schedule_update_ha_state()


class CO2MiniSensor(Entity):
    """Object for the individual sensors of the device."""

    def __init__(self, name, unit_of_measurement):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._name = name
        self._unit_of_measurement = unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @state.setter
    def state(self, newstate):
        """Set the new state of the entity."""
        self._state = newstate

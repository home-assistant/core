"""
A component which show the value of temperature, humidity and pressure
from Sense HAT board in the form of platform with graphs in history.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/
"""

import os
import logging
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import JobPriority
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


def get_cpu_temp():
    """get CPU temperature."""
    res = os.popen("vcgencmd measure_temp").readline()
    t_cpu = float(res.replace("temp=", "").replace("'C\n", ""))
    return t_cpu


def get_average(temp_base):
    """use moving average to get better readings."""
    if not hasattr(get_average, "temp"):
        get_average.temp = [temp_base, temp_base, temp_base]
    get_average.temp[2] = get_average.temp[1]
    get_average.temp[1] = get_average.temp[0]
    get_average.temp[0] = temp_base
    temp_avg = (get_average.temp[0]+get_average.temp[1]+get_average.temp[2])/3
    return temp_avg


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    add_devices([addtemperature(hass)])
    add_devices([addhumidity(hass)])
    add_devices([addpressure(hass)])


class addtemperature(Entity):
    """Representation of a Temperature Sensor."""
    def __init__(self, hass):
        """Initialize the sensor."""
        self._temp = None
        """Get initial state."""
        hass.pool.add_job(
            JobPriority.EVENT_STATE, (self.update_ha_state, True))

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Temperature'

    @property
    def state(self):
        """Return state of the sensor."""
        return self._temp

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self, *args):
        """Get the latest data."""
        from sense_hat import SenseHat
        sense = SenseHat()
        temp_from_h = sense.get_temperature_from_humidity()
        temp_from_p = sense.get_temperature_from_pressure()
        t_cpu = get_cpu_temp()
        t_total = (temp_from_h+temp_from_p)/2
        t_correct = t_total - ((t_cpu-t_total)/1.5)
        t_correct = get_average(t_correct)
        self._temp = t_correct


class addhumidity(Entity):
    """Representation of a Humidity Sensor."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self._humidity = None
        """Get initial state."""
        hass.pool.add_job(
            JobPriority.EVENT_STATE, (self.update_ha_state, True))

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Humidity'

    @property
    def state(self):
        """Return state of the sensor."""
        return self._humidity

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return '%'

    def update(self, *args):
        """Get the latest data."""
        from sense_hat import SenseHat
        sense = SenseHat()
        self._humidity = sense.get_humidity()


class addpressure(Entity):
    """Representation of a Pressure Sensor."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self._pressure = None
        """Get initial state."""
        hass.pool.add_job(
            JobPriority.EVENT_STATE, (self.update_ha_state, True))

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Pressure'

    @property
    def state(self):
        """Return state of the sensor."""
        return self._pressure

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'mb'

    def update(self, *args):
        """Get the latest data."""
        from sense_hat import SenseHat
        sense = SenseHat()
        self._pressure = sense.get_pressure()

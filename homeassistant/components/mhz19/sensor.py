"""Support for CO2 sensor connected to a serial port."""
from datetime import timedelta
import logging

from pmsensor import co2sensor
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.temperature import celsius_to_fahrenheit

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_DEVICE = "serial_device"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

DEFAULT_NAME = "CO2 Sensor"

ATTR_CO2_CONCENTRATION = "co2_concentration"

SENSOR_TEMPERATURE = "temperature"
SENSOR_CO2 = "co2"
SENSOR_TYPES = {
    SENSOR_TEMPERATURE: ["Temperature", None],
    SENSOR_CO2: ["CO2", CONCENTRATION_PARTS_PER_MILLION],
}
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_SERIAL_DEVICE): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[SENSOR_CO2]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available CO2 sensors."""

    try:
        co2sensor.read_mh_z19(config.get(CONF_SERIAL_DEVICE))
    except OSError as err:
        _LOGGER.error(
            "Could not open serial connection to %s (%s)",
            config.get(CONF_SERIAL_DEVICE),
            err,
        )
        return False
    SENSOR_TYPES[SENSOR_TEMPERATURE][1] = hass.config.units.temperature_unit

    data = MHZClient(co2sensor, config.get(CONF_SERIAL_DEVICE))
    dev = []
    name = config.get(CONF_NAME)

    for variable in config[CONF_MONITORED_CONDITIONS]:
        dev.append(MHZ19Sensor(data, variable, SENSOR_TYPES[variable][1], name))

    add_entities(dev, True)
    return True


class MHZ19Sensor(Entity):
    """Representation of an CO2 sensor."""

    def __init__(self, mhz_client, sensor_type, temp_unit, name):
        """Initialize a new PM sensor."""
        self._mhz_client = mhz_client
        self._sensor_type = sensor_type
        self._temp_unit = temp_unit
        self._name = name
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._ppm = None
        self._temperature = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}: {SENSOR_TYPES[self._sensor_type][0]}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._ppm if self._sensor_type == SENSOR_CO2 else self._temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Read from sensor and update the state."""
        self._mhz_client.update()
        data = self._mhz_client.data
        self._temperature = data.get(SENSOR_TEMPERATURE)
        if self._temperature is not None and self._temp_unit == TEMP_FAHRENHEIT:
            self._temperature = round(celsius_to_fahrenheit(self._temperature), 1)
        self._ppm = data.get(SENSOR_CO2)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        result = {}
        if self._sensor_type == SENSOR_TEMPERATURE and self._ppm is not None:
            result[ATTR_CO2_CONCENTRATION] = self._ppm
        if self._sensor_type == SENSOR_CO2 and self._temperature is not None:
            result[ATTR_TEMPERATURE] = self._temperature
        return result


class MHZClient:
    """Get the latest data from the MH-Z sensor."""

    def __init__(self, co2sens, serial):
        """Initialize the sensor."""
        self.co2sensor = co2sens
        self._serial = serial
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data the MH-Z19 sensor."""
        self.data = {}
        try:
            result = self.co2sensor.read_mh_z19_with_temperature(self._serial)
            if result is None:
                return
            co2, temperature = result

        except OSError as err:
            _LOGGER.error(
                "Could not open serial connection to %s (%s)", self._serial, err
            )
            return

        if temperature is not None:
            self.data[SENSOR_TEMPERATURE] = temperature
        if co2 is not None and 0 < co2 <= 5000:
            self.data[SENSOR_CO2] = co2

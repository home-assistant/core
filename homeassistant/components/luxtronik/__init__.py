"""Support for Luxtronik heatpump controllers."""
from datetime import timedelta
import logging

from luxtronik import LOGGER as LuxLogger, Luxtronik as Lux
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

from .const import (
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_CALCULATIONS,
    CONF_PARAMETERS,
    CONF_SAFE,
    CONF_VISIBILITIES,
)

LuxLogger.setLevel(level="WARNING")


_LOGGER = logging.getLogger(__name__)


DATA_LUXTRONIK = "DATA_LT"

LUXTRONIK_PLATFORMS = ["binary_sensor", "sensor"]
DOMAIN = "luxtronik"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SERVICE_WRITE = "write"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=8889): cv.port,
                vol.Optional(CONF_SAFE, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PARAMETER): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(cv.Number, cv.string),
    }
)


def setup(hass, config):
    """Set up the Luxtronik component."""
    conf = config[DOMAIN]

    host = conf["CONF_HOST"]
    port = conf["CONF_PORT"]
    safe = conf["CONF_SAFE"]

    luxtronik = LuxtronikDevice(host, port, safe)

    hass.data[DATA_LUXTRONIK] = luxtronik

    def write_parameter(service):
        """Write a parameter to the Luxtronik heatpump."""
        parameter = service.data.get(ATTR_PARAMETER)
        value = service.data.get(ATTR_VALUE)
        luxtronik.write(parameter, value)

    hass.services.register(
        DOMAIN, SERVICE_WRITE, write_parameter, schema=SERVICE_WRITE_SCHEMA
    )

    return True


class LuxtronikDevice:
    """Handle all communication with Luxtronik."""

    def __init__(self, host, port, safe):
        """Initialize the Luxtronik connection."""

        self._host = host
        self._port = port
        self._luxtronik = Lux(host, port, safe)
        self.update()

    def get_sensor(self, group, sensor_id):
        """Get sensor by configured sensor ID."""
        sensor = None
        if group == CONF_PARAMETERS:
            sensor = self._luxtronik.parameters.get(sensor_id)
        if group == CONF_CALCULATIONS:
            sensor = self._luxtronik.calculations.get(sensor_id)
        if group == CONF_VISIBILITIES:
            sensor = self._luxtronik.visibilities.get(sensor_id)
        return sensor

    def write(self, parameter, value):
        """Write a parameter to the Luxtronik heatpump."""
        self._luxtronik.parameters.set(parameter, value)
        self._luxtronik.write()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the data from Luxtronik."""
        self._luxtronik.read()

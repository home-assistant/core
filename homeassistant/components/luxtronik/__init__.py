"""Support for Luxtronik heatpump controllers."""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_PARAMETER = "parameter"
ATTR_VALUE = "value"

CONF_SENSORS = "sensors"
CONF_ID = "id"
CONF_INVERT_STATE = "invert"
CONF_SAFE = "safe"
CONF_GROUP = "group"
CONF_PARAMETERS = "parameters"
CONF_CALCULATIONS = "calculations"
CONF_VISIBILITIES = "visibilities"

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
                vol.Required(CONF_HOST, default=""): cv.string,
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

    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    safe = conf.get(CONF_SAFE)

    luxtronik = Luxtronik(host, port, safe)
    luxtronik.update()

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


class Luxtronik:
    """Handle all communication with Luxtronik."""

    def __init__(self, host, port, safe=True):
        """Initialize the Luxtronik connection."""
        from luxtronik import Luxtronik as Lux

        from luxtronik import LOGGER as LuxLogger

        LuxLogger.setLevel(level="WARNING")

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

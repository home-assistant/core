"""Support gathering ted5000 information."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, POWER_WATT, UNIT_VOLT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ted"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ted5000 sensor."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    url = f"http://{host}:{port}/api/LiveData.xml"

    gateway = Ted5000Gateway(url)

    # Get MUT information to create the sensors.
    gateway.update()

    dev = []
    for mtu in gateway.data:
        dev.append(Ted5000Sensor(gateway, name, mtu, POWER_WATT))
        dev.append(Ted5000Sensor(gateway, name, mtu, UNIT_VOLT))

    add_entities(dev)
    return True


class Ted5000Sensor(Entity):
    """Implementation of a Ted5000 sensor."""

    def __init__(self, gateway, name, mtu, unit):
        """Initialize the sensor."""
        units = {POWER_WATT: "power", UNIT_VOLT: "voltage"}
        self._gateway = gateway
        self._name = "{} mtu{} {}".format(name, mtu, units[unit])
        self._mtu = mtu
        self._unit = unit
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def state(self):
        """Return the state of the resources."""
        try:
            return self._gateway.data[self._mtu][self._unit]
        except KeyError:
            pass

    def update(self):
        """Get the latest data from REST API."""
        self._gateway.update()


class Ted5000Gateway:
    """The class for handling the data retrieval."""

    def __init__(self, url):
        """Initialize the data object."""
        self.url = url
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Ted5000 XML API."""

        try:
            request = requests.get(self.url, timeout=10)
        except requests.exceptions.RequestException as err:
            _LOGGER.error("No connection to endpoint: %s", err)
        else:
            doc = xmltodict.parse(request.text)
            mtus = int(doc["LiveData"]["System"]["NumberMTU"])

            for mtu in range(1, mtus + 1):
                power = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerNow"])
                voltage = int(doc["LiveData"]["Voltage"]["MTU%d" % mtu]["VoltageNow"])

                self.data[mtu] = {POWER_WATT: power, UNIT_VOLT: voltage / 10}

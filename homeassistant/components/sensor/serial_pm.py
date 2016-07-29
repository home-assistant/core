"""
Support for particulate matter sensors connected to a serial port.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.particulate_matter/
"""
import logging
import threading
import time
from datetime import timedelta

import voluptuous as vol

from homeassistant.util import Throttle
from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_SCAN_INTERVAL
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pmsensor==0.2']

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_DEVICE = "serial_device"
CONF_BRAND = "brand"
#SCAN_INTERVAL = timedelta(minutes=10)
SCAN_INTERVAL = 10

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'serial_pm',
    vol.Optional(CONF_NAME, default=""): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=300): cv.positive_int,
    vol.Required(CONF_SERIAL_DEVICE): cv.string,
    vol.Required(CONF_BRAND): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1))
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available PM sensors."""

    from pmsensor import serial_data_collector as pm

    #SCAN_INTERVAL.minutes = config.get(CONF_SCAN_INTERVAL)

    try:
        coll = pm.PMDataCollector(config.get(CONF_SERIAL_DEVICE),
                                  pm.SUPPORTED_SENSORS[config.get(CONF_BRAND)])
    except KeyError:
        _LOGGER.error("Brand %s not supported", config.get(CONF_BRAND))
        _LOGGER.error(" supported brands: ", pm.SUPPORTED_SENSORS)

    dev = []

    for pmname in coll.supported_values():
        if config.get("name") != "":
            name = "{} PM{}".format(config.get("name"), pmname)
        else:
            name = "PM{}".format(pmname)
        dev.append(ParticulateMatterSensor(coll, name, pmname))

    add_devices(dev)


class ParticulateMatterSensor(Entity):
    """Representation of an Particulate matter sensor."""

    # pylint: disable=too-many-arguments

    def __init__(self, pmDataCollector, name, pmname):
        """Initialize a new PM sensor."""
        self._name = name
        self._pmname = pmname
        self._state = None
        self._collector = pmDataCollector

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "µg/m³"

    #@Throttle(SCAN_INTERVAL)
    def update(self):
        """Read from sensor and update the state"""
        _LOGGER.debug("Reading data from PM sensor")
        try:
            self._state = self._collector.read_data()[self._pmname]
        except KeyError:
            _LOGGER.error("Could not read PM%s value", self._pmname)

    def should_poll(self):
        """Sensor needs polling."""
        return True

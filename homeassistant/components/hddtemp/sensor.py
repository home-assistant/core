"""Support for getting the disk temperature of a host."""
from datetime import timedelta
import logging
import socket
from telnetlib import Telnet

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_DISKS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = "device"
ATTR_MODEL = "model"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7634
DEFAULT_NAME = "HD Temperature"
DEFAULT_TIMEOUT = 5

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DISKS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HDDTemp sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    disks = config.get(CONF_DISKS)

    hddtemp = HddTempData(host, port)
    hddtemp.update()

    if not disks:
        disks = [next(iter(hddtemp.data)).split("|")[0]]

    dev = []
    for disk in disks:
        dev.append(HddTempSensor(name, disk, hddtemp))

    add_entities(dev, True)


class HddTempSensor(SensorEntity):
    """Representation of a HDDTemp sensor."""

    def __init__(self, name, disk, hddtemp):
        """Initialize a HDDTemp sensor."""
        self.hddtemp = hddtemp
        self.disk = disk
        self._name = f"{name} {disk}"
        self._state = None
        self._details = None
        self._unit = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._details is not None:
            return {ATTR_DEVICE: self._details[0], ATTR_MODEL: self._details[1]}

    def update(self):
        """Get the latest data from HDDTemp daemon and updates the state."""
        self.hddtemp.update()

        if self.hddtemp.data and self.disk in self.hddtemp.data:
            self._details = self.hddtemp.data[self.disk].split("|")
            self._state = self._details[2]
            if self._details is not None and self._details[3] == "F":
                self._unit = TEMP_FAHRENHEIT
            else:
                self._unit = TEMP_CELSIUS
        else:
            self._state = None


class HddTempData:
    """Get the latest data from HDDTemp and update the states."""

    def __init__(self, host, port):
        """Initialize the data object."""
        self.host = host
        self.port = port
        self.data = None

    def update(self):
        """Get the latest data from HDDTemp running as daemon."""
        try:
            connection = Telnet(host=self.host, port=self.port, timeout=DEFAULT_TIMEOUT)
            data = (
                connection.read_all()
                .decode("ascii")
                .lstrip("|")
                .rstrip("|")
                .split("||")
            )
            self.data = {data[i].split("|")[0]: data[i] for i in range(0, len(data), 1)}
        except ConnectionRefusedError:
            _LOGGER.error("HDDTemp is not available at %s:%s", self.host, self.port)
            self.data = None
        except socket.gaierror:
            _LOGGER.error("HDDTemp host not found %s:%s", self.host, self.port)
            self.data = None

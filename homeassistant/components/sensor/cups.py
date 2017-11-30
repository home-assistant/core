"""
Details about printers which are connected to CUPS.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.cups/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pycups==1.9.73']

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_URI = 'device_uri'
ATTR_PRINTER_INFO = 'printer_info'
ATTR_PRINTER_IS_SHARED = 'printer_is_shared'
ATTR_PRINTER_LOCATION = 'printer_location'
ATTR_PRINTER_MODEL = 'printer_model'
ATTR_PRINTER_STATE_MESSAGE = 'printer_state_message'
ATTR_PRINTER_STATE_REASON = 'printer_state_reason'
ATTR_PRINTER_TYPE = 'printer_type'
ATTR_PRINTER_URI_SUPPORTED = 'printer_uri_supported'

CONF_PRINTERS = 'printers'

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 631

ICON = 'mdi:printer'

SCAN_INTERVAL = timedelta(minutes=1)

PRINTER_STATES = {
    3: 'idle',
    4: 'printing',
    5: 'stopped',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PRINTERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the CUPS sensor."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    printers = config.get(CONF_PRINTERS)

    try:
        data = CupsData(host, port)
        data.update()
    except RuntimeError:
        _LOGGER.error("Unable to connect to CUPS server: %s:%s", host, port)
        return False

    dev = []
    for printer in printers:
        if printer in data.printers:
            dev.append(CupsSensor(data, printer))
        else:
            _LOGGER.error("Printer is not present: %s", printer)
            continue

    add_devices(dev, True)


class CupsSensor(Entity):
    """Representation of a CUPS sensor."""

    def __init__(self, data, printer):
        """Initialize the CUPS sensor."""
        self.data = data
        self._name = printer
        self._printer = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._printer is not None:
            try:
                return next(v for k, v in PRINTER_STATES.items()
                            if self._printer['printer-state'] == k)
            except StopIteration:
                return self._printer['printer-state']

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._printer is not None:
            return {
                ATTR_DEVICE_URI: self._printer['device-uri'],
                ATTR_PRINTER_INFO: self._printer['printer-info'],
                ATTR_PRINTER_IS_SHARED: self._printer['printer-is-shared'],
                ATTR_PRINTER_LOCATION: self._printer['printer-location'],
                ATTR_PRINTER_MODEL: self._printer['printer-make-and-model'],
                ATTR_PRINTER_STATE_MESSAGE:
                    self._printer['printer-state-message'],
                ATTR_PRINTER_STATE_REASON:
                    self._printer['printer-state-reasons'],
                ATTR_PRINTER_TYPE: self._printer['printer-type'],
                ATTR_PRINTER_URI_SUPPORTED:
                    self._printer['printer-uri-supported'],
            }

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._printer = self.data.printers.get(self._name)


# pylint: disable=import-error
class CupsData(object):
    """Get the latest data from CUPS and update the state."""

    def __init__(self, host, port):
        """Initialize the data object."""
        self._host = host
        self._port = port
        self.printers = None

    def update(self):
        """Get the latest data from CUPS."""
        from cups import Connection

        conn = Connection(host=self._host, port=self._port)
        self.printers = conn.getPrinters()

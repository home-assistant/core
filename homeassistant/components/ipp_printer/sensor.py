"""Status and ink/toner levels of one or more IPP printers."""
import importlib
import logging
from datetime import timedelta
from urllib.parse import urlparse

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_PRINTERS = 'printers'

DEFAULT_PORT = 631

ICON_PRINTER = 'mdi:printer'
ICON_MARKER = 'mdi:water'

SCAN_INTERVAL = timedelta(minutes=1)

ATTR_MARKER_TYPE = 'marker_type'
ATTR_MARKER_LOW_LEVEL = 'marker_low_level'
ATTR_MARKER_HIGH_LEVEL = 'marker_high_level'
ATTR_PRINTER_NAME = 'printer_name'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PRINTERS): vol.All(cv.ensure_list, [cv.string])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the IPP platform."""

    printers = config.get(CONF_PRINTERS)

    dev = []
    for printer in printers:
        try:
            data = IPPData(printer)
            data.update()
        except RuntimeError:
            _LOGGER.error("Unable to connect to IPP printer: %s", printer)
            continue

        dev.append(PrinterSensor(data, data.attributes['printer-make-and-model']))

        if data.attributes["marker-names"] is not None:
            for marker in data.attributes["marker-names"]:
                index = data.attributes['marker-names'].index(marker)
                dev.append(MarkerSensor(data, marker, index))

    add_entities(dev, True)


class MarkerSensor(Entity):
    """Implementation of the MarkerSensor, which represents the percentage of ink or toner."""

    def __init__(self, data, name, index):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._index = index
        self._attributes = None

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON_MARKER

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._attributes is not None:
            return self._attributes['marker-levels'][self._index]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._attributes is not None:
            high_level = self._attributes['marker-high-levels']
            if isinstance(high_level, list):
                high_level = high_level[self._index]

            low_level = self._attributes['marker-low-levels']
            if isinstance(low_level, list):
                low_level = low_level[self._index]

            marker_types = self._attributes['marker-types']
            if isinstance(marker_types, list):
                marker_types = marker_types[self._index]

            return {
                ATTR_MARKER_HIGH_LEVEL: high_level,
                ATTR_MARKER_LOW_LEVEL: low_level,
                ATTR_MARKER_TYPE: marker_types,
                ATTR_PRINTER_NAME: self._attributes['printer-make-and-model']
            }

    def update(self):
        """Update the state of the sensor.
        Data fetching is done by PrinterSensor"""
        self._attributes = self.data.attributes


class PrinterSensor(Entity):
    """Implementation of the PrinterSensor, which represents the status of the printer."""

    def __init__(self, data, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._status = None

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON_PRINTER

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._status is not None:
            return self._status

    def update(self):
        """Fetch new state data for the sensor.
        """
        try:
            self.data.update()
            status = self.data.attributes["printer-state"]

            if status == 3:
                self._status = "Ready"
            elif status == 4:
                self._status = "Printing"
            elif status == 5:
                self._status = "Stopped"
            else:
                self._status = "Unknown"
        except RuntimeError:
            self._status = "Offline"
            return False


class IPPData:
    """Get the latest data from the IPP printer and update the state."""

    def __init__(self, printer):
        """Initialize the data object."""
        parsed_url = urlparse(printer)
        self._host = parsed_url.hostname

        self._port = parsed_url.port
        if self._port is None:
            self._port = DEFAULT_PORT

        self._printer = printer
        self.attributes = None

    def update(self):
        """Get the latest data from the IPP printer using the CUPS library."""
        cups = importlib.import_module('cups')

        conn = cups.Connection(host=self._host, port=self._port)
        self.attributes = conn.getPrinterAttributes(uri=self._printer)

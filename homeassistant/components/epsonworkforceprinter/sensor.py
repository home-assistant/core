"""Support for Epson Workforce Printer."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['epsonprinter==0.0.8']

_LOGGER = logging.getLogger(__name__)
DEFAULT_IP = '127.0.0.1'
MONITORED_CONDITIONS = {
    'black': ['Inklevel Black', '%', 'mdi:water'],
    'magenta': ['Inklevel Magenta', '%', 'mdi:water'],
    'cyan': ['Inklevel Cyan', '%', 'mdi:water'],
    'yellow': ['Inklevel Yellow', '%', 'mdi:water'],
    'clean': ['Inklevel Cleaning', '%', 'mdi:water'],
}
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_IP): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
})
SCAN_INTERVAL = timedelta(minutes=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the cartridge sensor."""
    host = config.get(CONF_HOST)

    from epsonprinter_pkg.epsonprinterapi import EpsonPrinterAPI
    api = EpsonPrinterAPI(host)

    sensors = [EpsonPrinterCartridge(hass, api, condition)
               for condition in config[CONF_MONITORED_CONDITIONS]]

    add_devices(sensors, True)


class EpsonPrinterCartridge(Entity):
    """Representation of a cartdige sensor."""

    def __init__(self, hass, api, variable):
        """Initialize a cartridge sensor."""
        self._hass = hass
        self._api = api

        variable_info = MONITORED_CONDITIONS[variable]
        self._var_name = variable_info[0]
        self._var_id = variable
        self._var_unit = variable_info[1]
        self._var_icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._var_name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._var_unit

    @property
    def state(self):
        """Return the state of the device."""
        return self._api.getSensorValue(self._var_id)

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._api.available

    def update(self):
        """Get the latest data from the Epson printer."""
        self._api.update()


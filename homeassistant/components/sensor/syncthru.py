"""
Support for Samsung Printers with SyncThru web interface.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.syncthru/
"""

import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_RESOURCE, CONF_HOST, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

REQUIREMENTS = ['pysyncthru==0.3.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Samsung Printer'
DEFAULT_MONITORED_CONDITIONS = [
    'toner_black',
    'toner_cyan',
    'toner_magenta',
    'toner_yellow',
    'drum_black',
    'drum_cyan',
    'drum_magenta',
    'drum_yellow',
    'tray_1',
    'tray_2',
    'tray_3',
    'tray_4',
    'tray_5',
    'output_tray_0',
    'output_tray_1',
    'output_tray_2',
    'output_tray_3',
    'output_tray_4',
    'output_tray_5',
]
COLORS = [
    'black',
    'cyan',
    'magenta',
    'yellow'
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(
        CONF_NAME,
        default=DEFAULT_NAME
    ): cv.string,
    vol.Optional(
        CONF_MONITORED_CONDITIONS,
        default=DEFAULT_MONITORED_CONDITIONS
    ): vol.All(cv.ensure_list, [vol.In(DEFAULT_MONITORED_CONDITIONS)])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SyncThru component."""
    from pysyncthru import SyncThru, test_syncthru

    if discovery_info is not None:
        host = discovery_info.get(CONF_HOST)
        name = discovery_info.get(CONF_NAME, DEFAULT_NAME)
        _LOGGER.debug("Discovered a new Samsung Printer: %s", discovery_info)
        # Test if the discovered device actually is a syncthru printer
        if not test_syncthru(host):
            _LOGGER.error("No SyncThru Printer found at %s", host)
            return
        monitored = DEFAULT_MONITORED_CONDITIONS
    else:
        host = config.get(CONF_RESOURCE)
        name = config.get(CONF_NAME)
        monitored = config.get(CONF_MONITORED_CONDITIONS)

    # Main device, always added
    try:
        printer = SyncThru(host)
    except TypeError:
        # if an exception is thrown, printer cannot be set up
        return

    printer.update()
    devices = [SyncThruMainSensor(printer, name)]

    for key in printer.toner_status(filter_supported=True):
        if 'toner_{}'.format(key) in monitored:
            devices.append(SyncThruTonerSensor(printer, name, key))
    for key in printer.drum_status(filter_supported=True):
        if 'drum_{}'.format(key) in monitored:
            devices.append(SyncThruDrumSensor(printer, name, key))
    for key in printer.input_tray_status(filter_supported=True):
        if 'tray_{}'.format(key) in monitored:
            devices.append(SyncThruInputTraySensor(printer, name, key))
    for key in printer.output_tray_status():
        if 'output_tray_{}'.format(key) in monitored:
            devices.append(SyncThruOutputTraySensor(printer, name, key))

    add_entities(devices, True)


class SyncThruSensor(Entity):
    """Implementation of an abstract Samsung Printer sensor platform."""

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        self.syncthru = syncthru
        self._attributes = {}
        self._state = None
        self._name = name
        self._icon = 'mdi:printer'
        self._unit_of_measurement = None
        self._id_suffix = ''

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        serial = self.syncthru.serial_number()
        return serial + self._id_suffix if serial else super().unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the device."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measuremnt."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes


class SyncThruMainSensor(SyncThruSensor):
    """Implementation of the main sensor, monitoring the general state."""

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._id_suffix = '_main'

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        self.syncthru.update()
        self._state = self.syncthru.device_status()


class SyncThruTonerSensor(SyncThruSensor):
    """Implementation of a Samsung Printer toner sensor platform."""

    def __init__(self, syncthru, name, color):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = "{} Toner {}".format(name, color)
        self._color = color
        self._unit_of_measurement = '%'
        self._id_suffix = '_toner_{}'.format(color)

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.toner_status(
                ).get(self._color, {})
            self._state = self._attributes.get('remaining')


class SyncThruDrumSensor(SyncThruSensor):
    """Implementation of a Samsung Printer toner sensor platform."""

    def __init__(self, syncthru, name, color):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = "{} Drum {}".format(name, color)
        self._color = color
        self._unit_of_measurement = '%'
        self._id_suffix = '_drum_{}'.format(color)

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.drum_status(
                ).get(self._color, {})
            self._state = self._attributes.get('remaining')


class SyncThruInputTraySensor(SyncThruSensor):
    """Implementation of a Samsung Printer input tray sensor platform."""

    def __init__(self, syncthru, name, number):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = "{} Tray {}".format(name, number)
        self._number = number
        self._id_suffix = '_tray_{}'.format(number)

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.input_tray_status(
                ).get(self._number, {})
            self._state = self._attributes.get('newError')
            if self._state == '':
                self._state = 'Ready'


class SyncThruOutputTraySensor(SyncThruSensor):
    """Implementation of a Samsung Printer input tray sensor platform."""

    def __init__(self, syncthru, name, number):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._name = "{} Output Tray {}".format(name, number)
        self._number = number
        self._id_suffix = '_output_tray_{}'.format(number)

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.is_online():
            self._attributes = self.syncthru.output_tray_status(
                ).get(self._number, {})
            self._state = self._attributes.get('status')
            if self._state == '':
                self._state = 'Ready'

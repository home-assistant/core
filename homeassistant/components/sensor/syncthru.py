"""
Connect to a Samsung Printer via it's SyncThru
 web interface and read data
"""
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_RESOURCE, STATE_UNKNOWN, CONF_HOST, CONF_NAME, CONF_FRIENDLY_NAME,
    CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

REQUIREMENTS = ['pysyncthru==0.2.2']

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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SyncThru component."""
    from pysyncthru import SyncThru, test_syncthru

    if discovery_info is not None:
        host = discovery_info.get(CONF_HOST)
        name = discovery_info.get(CONF_NAME, DEFAULT_NAME)
        _LOGGER.debug("Discovered a new Samsung Printer: %s" % discovery_info)
        # Test if the discovered device actually is a syncthru printer
        if not test_syncthru(host):
            _LOGGER.error("No SyncThru Printer found at %s" % host)
            return False
        monitored = DEFAULT_MONITORED_CONDITIONS
    else:
        host = config.get(CONF_RESOURCE)
        name = config.get(CONF_NAME)
        monitored = config.get(CONF_MONITORED_CONDITIONS)

    # Main device, always added
    printer = SyncThru(host)
    printer.update()
    devices = [SyncThruMain(hass, printer, name)]

    for key in printer.tonerStatus(filter_supported=True).keys():
        if 'toner_' + str(key) in monitored:
            devices.append(SyncThruToner(hass, printer, name, key))
    for key in printer.drumStatus(filter_supported=True).keys():
        if 'drum_' + str(key) in monitored:
            devices.append(SyncThruDrum(hass, printer, name, key))
    for key in printer.inputTrayStatus(filter_supported=True).keys():
        if 'tray_' + str(key) in monitored:
            devices.append(SyncThruInputTray(hass, printer, name, key))
    for key in printer.outputTrayStatus().keys():
        if 'output_tray_' + str(key) in monitored:
            devices.append(SyncThruOutputTray(hass, printer, name, key))

    add_devices(devices, True)
    return True

class SyncThruSensor(Entity):
    """Implementation of an abstract Samsung Printer sensor platform."""

    def __init__(self, hass, syncthru, name):
        """Initialize the sensor"""
        self._hass = hass
        self.syncthru = syncthru
        self._attributes = {}
        self._state = STATE_UNKNOWN
        self._name = name
        self._icon = 'mdi:printer'
        self._unit_of_measurement = None

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
        """Return the unit of measuremnt"""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes


class SyncThruMain(SyncThruSensor):

    def __init__(self, hass, syncthru, name):
        """Initialize the sensor"""
        super.__init__(hass, syncthru, name)

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        self.syncthru.update()
        self._state = self.syncthru.deviceStatus()

        if self.syncthru.isOnline():
            self._attributes[CONF_FRIENDLY_NAME] = self.syncthru.model()
            self._state = self.syncthru.deviceStatus()


class SyncThruToner(SyncThruSensor):
    """Implementation of a Samsung Printer toner sensor platform."""

    def __init__(self, hass, syncthru, name, color):
        """Initialize the sensor"""
        super.__init__(hass, syncthru, name)
        self._name = "{} toner {}".format(name, color)
        self._color = color
        self._unit_of_measurement = '%'

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor
        
        if self.syncthru.isOnline():
            self._attributes = self.syncthru.tonerStatus(
                ).get(self._color, {})
            self._state = self._attributes.get(
                'remaining', STATE_UNKNOWN)
            self._attributes[CONF_FRIENDLY_NAME] = "{} Toner {}".format(
                self._color, self.syncthru.model())

class SyncThruDrum(SyncThruSensor):
    """Implementation of a Samsung Printer toner sensor platform."""

    def __init__(self, hass, syncthru, name, color):
        """Initialize the sensor"""
        super.__init__(hass, syncthru, name)
        self._name = "{} drum {}".format(name, color)
        self._color = color
        self._unit_of_measurement = '%'

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.isOnline():
            self._attributes = self.syncthru.drumStatus(
                ).get(self._color, {})
            self._state = self._attributes.get(
                'remaining', STATE_UNKNOWN)
            self._attributes[CONF_FRIENDLY_NAME] = "{} Drum {}".format(
                self._color, self.syncthru.model())

class SyncThruInputTray(SyncThruSensor):
    """Implementation of a Samsung Printer input tray sensor platform."""

    def __init__(self, hass, syncthru, name, number):
        """Initialize the sensor"""
        super.__init__(hass, syncthru, name)
        self._name = "{} tray {}".format(name, number)
        self._number = number

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor
        
        if self.syncthru.isOnline():
            self._attributes = self.syncthru.inputTrayStatus(
                ).get(self._number, {})
            self._state = self._attributes.get(
                'newError', STATE_UNKNOWN)
            if self._state == '':
                self._state = 'Ready'
            self._attributes[CONF_FRIENDLY_NAME] = "Tray {} {}".format(
                self._number, self.syncthru.model())

class SyncThruOutputTray(SyncThruSensor):
    """Implementation of a Samsung Printer input tray sensor platform."""

    def __init__(self, hass, syncthru, name, number):
        """Initialize the sensor"""
        super.__init__(hass, syncthru, name)
        self._name = "{} output tray {}".format(name, number)
        self._number = number

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        # Data fetching is taken care of through the Main sensor

        if self.syncthru.isOnline():
            self._attributes = self.syncthru.outputTrayStatus(
                ).get(self._number, {})
            self._state = self._attributes.get(
                'status', STATE_UNKNOWN)
            if self._state == '':
                self._state = 'Ready'
            self._attributes[CONF_FRIENDLY_NAME] = "Output Tray {} {}".format(
                self._number, self.syncthru.model())

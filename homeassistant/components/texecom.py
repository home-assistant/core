"""
Support for Texecom Alarm Panels & Devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/texecom/
"""
import asyncio
import logging
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyserial-asyncio==0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'texecom'

DATA_EVL = 'texecom'

CONF_PORT = 'port'
CONF_PANELUUID = 'uuid'
CONF_ZONENAME = "name"
CONF_ZONES = 'zones'
CONF_ZONETYPE = 'type'
CONF_ZONENUMBER = 'panelzone'

DEFAULT_PORT = '/dev/ttys0'
DEFAULT_ZONENAME = 'zone'
DEFAULT_ZONES = 'zones'
DEFAULT_ZONETYPE = 'motion'
DEFAULT_ZONENUMBER = '1'

SIGNAL_ZONE_UPDATE = 'texecom.zones_updated'

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONENAME): cv.string,
    vol.Required(CONF_ZONETYPE, default=DEFAULT_ZONETYPE): cv.string,
    vol.Required(CONF_ZONENUMBER): cv.string})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_PANELUUID): cv.string,
        vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up for Texecom devices."""
    conf = config.get(DOMAIN)
    port = conf.get(CONF_PORT)
    zones = conf.get(CONF_ZONES)

    _LOGGER.info('Setting up Serial Interface')
    if zones:
        hass.async_create_task(async_load_platform(
            hass, 'alarm_control_panel',
            'texecominterface', {CONF_PORT: port}, config
        ))

    _LOGGER.info('Setting up zones')

    # Load sub-components for Texecom
    if zones:
        hass.async_create_task(async_load_platform(
            hass, 'binary_sensor', 'texecom', {
                CONF_ZONES: zones
            }, config
        ))

    return True


class TexecomBinarySensor(BinarySensorDevice):
    """Representation of an Texecom Binary Sensor."""

    def __init__(self, name, zone_number, zone_name, zone_type, state):
        """Initialize the device."""
        self._number = zone_number
        self._name = zone_name
        self._sensor_type = zone_type
        self._state = state

        _LOGGER.debug('Setting up zone: %s', self._number)
        _LOGGER.debug('Setting up zone: %s', self._name)
        _LOGGER.debug('Setting up zone: %s', self._sensor_type)
        _LOGGER.debug('Setting up zone: %s', self._state)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_ZONE_UPDATE, self._update_callback)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return the name of the device."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @callback
    def _update_callback(self, data):
        """Update the zone's state, if needed."""
        _LOGGER.debug('Attempting to Update Zone %s', self._name)

        if self._number == data.signalledzone:
            _LOGGER.info('Correct zone found to update %s', self._name)
            _LOGGER.debug('The new state is %s', data.zonestate)

            if data.zonestate == '0':
                _LOGGER.debug('Setting zone state to false')
                self._state = False
            elif data.zonestate == '1':
                _LOGGER.debug('Setting zone state to true')
                self._state = True
            else:
                _LOGGER.debug('Unknown state assuming tamper')
                self._state = True

            _LOGGER.info('New Zone State is %s', self._state)
            self.async_schedule_update_ha_state()


class TexecomPanelInterface(Entity):
    """Representation of a Texecom Panel Interface."""

    def __init__(self, name, port):
        """Initialize the Texecom Panel Interface."""
        self._name = name
        self._state = None
        self._port = port
        self._baudrate = '19200'
        self._serial_loop_task = None
        self._attributes = []
        self.signalledzone = '0'
        self.zonestate = '0'

        _LOGGER.info('Setting up Serial: %s', name)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._serial_loop_task = self.hass.loop.create_task(
            self.serial_read(self._port, self._baudrate))

    @asyncio.coroutine
    def serial_read(self, device, rate, **kwargs):
        """Read the data from the port."""
        import serial_asyncio
        _LOGGER.info('Opening Serial Port')
        reader, _ = yield from serial_asyncio.open_serial_connection(
            url=device, baudrate=rate, **kwargs)
        _LOGGER.info('Opened Serial Port')
        while True:
            line = yield from reader.readline()
            _LOGGER.info('Data read: %s', line)
            line = line.decode('utf-8').strip()
            _LOGGER.debug('Decoded Data: %s', line)

            try:
                if line[1] == 'Z':
                    _LOGGER.debug('Zone Info Found')
                    signalledzone = line[2:5]
                    signalledzone = signalledzone.lstrip('0')
                    zonestate = line[5]
                    _LOGGER.info('Signalled Zone: %s', signalledzone)
                    _LOGGER.info('Zone State: %s', zonestate)
                    self.zonestate = zonestate
                    self.signalledzone = signalledzone
                    async_dispatcher_send(self.hass, SIGNAL_ZONE_UPDATE, self)

            except IndexError:
                _LOGGER.error('Index error malformed string recived')

    @asyncio.coroutine
    def stop_serial_read(self):
        """Close resources."""
        if self._serial_loop_task:
            self._serial_loop_task.cancel()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the attributes of the entity (if any JSON present)."""
        return self._attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

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

REQUIREMENTS = ['pyTexecom==0.1']

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
    })

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_PANELTYPE): cv.string,
        vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up for Texecom devices."""
    conf = config.get(DOMAIN)
    port = conf.get(CONF_PORT)
    zones = conf.get(CONF_ZONES)
    paneltype = conf.get(CONF_PANELTYPE)

    controller = TexeconPanelInterface('Panel Interface', port, paneltype)

    hass.data[DATA_EVL] = controller

    @callback
    def zones_updated_callback(data):
        """Handle zone updates."""
        _LOGGER.info("Texecom sent a zone update event. Updating zones...")
        async_dispatcher_send(hass, SIGNAL_ZONE_UPDATE, data)

    @callback
    def stop_texecom(event):
        """Shutdown Texecom connection and thread on exit."""
        _LOGGER.info("Shutting down Texecom")
        controller.stop()

    controller.callback_zone_state_change = zones_updated_callback

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_texecom)

    _LOGGER.info("Start Texecom.")
    controller.start()

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
        _LOGGER.debug('The new state is %s', data[self._number])

        if data[self._number] == '0':
            _LOGGER.debug('Setting zone state to false')
            self._state = False
        elif data[self._number] == '1':
            _LOGGER.debug('Setting zone state to true')
            self._state = True
        else:
            _LOGGER.debug('Unknown state assuming tamper')
            self._state = True

        _LOGGER.info('New Zone State is %s', self._state)
        self.async_schedule_update_ha_state()




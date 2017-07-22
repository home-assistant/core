"""
Support for iRobot Roomba connected vacuum cleaners.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/roomba/
"""
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/pschmitt/Roomba980-Python/archive/1.2.1.zip'
                '#Roomba980-Python==1.2.1']

DOMAIN = 'roomba'
ROOMBA_ROBOTS = 'roomba_robots'

CONF_HOSTNAME = 'hostname'
CONF_CERT = 'certificate'
CONF_CONTINUOUS = 'continuous'

DEFAULT_CERT = '/etc/ssl/certs/ca-certificates.crt'
DEFAULT_CONTINUOUS = False

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOSTNAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CERT, default=DEFAULT_CERT): cv.string,
        vol.Optional(CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Roomba component."""
    from roomba import Roomba

    roomba = Roomba(
        address=config[DOMAIN][CONF_HOSTNAME],
        blid=config[DOMAIN][CONF_USERNAME],
        password=config[DOMAIN][CONF_PASSWORD],
        cert_name=config[DOMAIN][CONF_CERT],
        continuous=config[DOMAIN][CONF_CONTINUOUS]
    )
    roomba_hub = RoombaHub(hass, config[DOMAIN], roomba)
    hass.data[ROOMBA_ROBOTS] = [roomba_hub]

    if not roomba_hub.login():
        _LOGGER.debug('Failed to communicate with Roomba')
        return False
    roomba_hub.update()
    for component in ['sensor', 'switch']:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class RoombaTimeoutError(Exception):
    """Roomba Timeout occurred."""

    pass


class RoombaHub(object):
    """A Roomba wrapper class."""

    def __init__(self, hass, config, roomba):
        """Initialize the Roomba hub."""
        self.config = config
        self._roomba = roomba
        self._hass = hass
        self._data = None

    def _wait_for_update(self, timeout=10):
        from time import sleep
        tries = 0
        # last_update = self._roomba.time
        # while last_update == self._roomba.time:
        while not self._roomba.master_state:
            _LOGGER.debug('No data received from Roomba yet')
            sleep(1)
            if tries > timeout:
                raise RoombaTimeoutError(
                    'No data received after {} seconds'.format(timeout))
                break
            tries = tries + 1
        _LOGGER.debug('Communication with roomba succeeded')

    def login(self):
        """Login to Roomba."""
        try:
            _LOGGER.debug('Trying to connect to Roomba')
            self._roomba.connect()
            self._wait_for_update()
            _LOGGER.debug('Roomba state: %s',
                          self._roomba.cleanMissionStatus_phase)
            # self._roomba.disconnect()
            return True
        except RoombaTimeoutError:
            _LOGGER.error('Unable to connect to Roomba')
            return False

    def send_command(self, command):
        """Send a command to the Roomba."""
        # self._roomba.connect()
        self._roomba.send_command(command)
        # self._roomba.disconnect()

    @Throttle(timedelta(seconds=5))
    def update(self):
        """Reconnect to Roomba to request data update."""
        _LOGGER.debug('Running Roomba update %s',
                      self._hass.data[ROOMBA_ROBOTS])
        # self._roomba.connect()
        # self.wait_for_update()
        from time import sleep
        sleep(3)
        self._data = {
            'state': self._roomba.master_state['state'].get('reported', None),
            'status': self._roomba.cleanMissionStatus_phase
        }
        # self._roomba.disconnect()

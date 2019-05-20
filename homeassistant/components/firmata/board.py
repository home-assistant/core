"""Code to handle a Firmata board"""
import asyncio
import copy
import logging

_LOGGER = logging.getLogger(__name__)

from pymata_aio.pymata_core import PymataCore

#from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

class FirmataBoard:
    """Manages a single Firmata board"""

    def __init__(self, hass, config):
        """Initialize the system."""
        self.config = config
        self.hass = hass
        self.available = True
        self.api = None
        self.name = config['name']
        self._prefix = DOMAIN + '.' + self.config['name'] + '_'

    async def async_setup(self, tries=0):
        """Set up a Firmata insrance based on parameters"""
        name = self.name
        hass = self.hass

        try:
            _LOGGER.info('Attempting Firmata connection for %s', self.name)
            self.api = await get_board(hass, self.config)
        except RuntimeError as err:
            _LOGGER.error('Error connecting with PyMata board %s: %s', self.name, repr(err))
            return False

        hass.states.async_set(self._prefix + 'FirmwareVersion', await self.api.get_firmware_version())
        hass.states.async_set(self._prefix + 'ProtocolVersion', await self.api.get_protocol_version())
        hass.states.async_set(self._prefix + 'PymataVersion', await self.api.get_pymata_version())

        _LOGGER.info('Firmata connection successful for %s', self.name)
        return True

    async def async_reset(self):
        """Reset this board to default state."""

        # If the board was never setup.
        if self.api is None:
            return True

        await self.api.shutdown()

        return True


async def get_board(hass, data):
    """Create a board object"""
    boardData = copy.copy(data)
    boardData.pop('name')
    boardData['port_discovery_exceptions'] = True
    board = PymataCore(**boardData)

    await board.start_aio()
    return board

class FirmataBoardPin(Entity):
    async def __init__(self, name, board, pin, mode, **kwargs):
        self._name = name or DEVICE_DEFAULT_NAME
        self._type = type
        self._pin = pin
        self._mode = mode
        self._board = hass.data[DOMAIN][board]
        self._kwargs = kwargs

        await setup_pin()

    async def setup_pin(self):
        self._mode = None
        self._state = False
        pass
    
    @property
    def should_poll(self):
        """No polling needed."""
        return False

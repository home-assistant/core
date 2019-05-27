"""Code to handle a Firmata board."""
import logging

from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import Entity
from pymata_aio.pymata_core import PymataCore

from .const import (CONF_ARDUINO_WAIT, CONF_HANDSHAKE, CONF_PORT, CONF_REMOTE,
                    CONF_SERIAL_PORT, CONF_SLEEP_TUNE, CONF_SWITCHES, DOMAIN)

_LOGGER = logging.getLogger(__name__)


class FirmataBoard:
    """Manages a single Firmata board."""

    def __init__(self, hass, name: str, config: dict):
        """Initialize the board."""
        self.config = config
        self.hass = hass
        self.available = True
        self.api = None
        self.name = name
        self.switches = []

    async def async_setup(self, tries=0):
        """Set up a Firmata instance."""
        try:
            _LOGGER.info('Attempting Firmata connection for %s', self.name)
            self.api = await get_board(self.config)
        except RuntimeError as err:
            _LOGGER.error('Error connecting with PyMata board %s: %s',
                          self.name, repr(err))
            return False

        if CONF_SWITCHES in self.config:
            self.switches = self.config[CONF_SWITCHES]

        _LOGGER.info('Firmata connection successful for %s', self.name)
        return True

    async def async_reset(self):
        """Reset the board to default state."""
        # If the board was never setup, continue.
        if self.api is None:
            return True

        await self.api.shutdown()

        return True


async def get_board(data: dict) -> dict:
    """Create a Pymata board object."""
    board_data = dict()

    if CONF_REMOTE in data:
        board_data['ip_address'] = data[CONF_HOST]
        if CONF_PORT in data[CONF_REMOTE]:
            board_data['ip_port'] = data[CONF_REMOTE][CONF_PORT]
        if CONF_HANDSHAKE in data[CONF_REMOTE]:
            board_data['ip_handshake'] = data[CONF_REMOTE][CONF_HANDSHAKE]
    else:
        board_data['com_port'] = data[CONF_SERIAL_PORT]

    if CONF_ARDUINO_WAIT in data:
        board_data['arduino_wait'] = data[CONF_ARDUINO_WAIT]
    if CONF_SLEEP_TUNE in data:
        board_data['sleep_tune'] = data[CONF_SLEEP_TUNE]

    board_data['port_discovery_exceptions'] = True

    board = PymataCore(**board_data)

    await board.start_aio()
    return board


class FirmataBoardPin(Entity):
    """Manages a single Firmata board pin."""

    def __init__(self, hass, name: str, board_name: str, pin: int, **kwargs):
        """Initialize the pin."""
        self.hass = hass
        self._name = name
        self._pin = pin
        self._state = None
        self._board_name = board_name
        self._board = hass.data[DOMAIN][self._board_name]
        self._conf = kwargs or dict()
        self._attributes = {
            'board': self._board_name,
            'pin': self._pin
        }
        self._attributes.update(self._conf)

    @property
    def name(self) -> str:
        """Get the name of the pin."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Return True because the board is always available."""
        return True

    @property
    def device_state_attributes(self) -> dict:
        """Return device specific state attributes."""
        return self._attributes

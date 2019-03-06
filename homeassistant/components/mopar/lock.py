"""Support for the Mopar vehicle lock."""
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.components.mopar import (
    DOMAIN as MOPAR_DOMAIN,
    SUCCESS_RESPONSE
)
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED

REQUIREMENTS = ['motorparts==1.1.0']

DEPENDENCIES = ['mopar']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Mopar lock platform."""
    data = hass.data[MOPAR_DOMAIN]
    add_entities([MoparLock(data, index)
                  for index, _ in enumerate(data.vehicles)], True)


class MoparLock(LockDevice):
    """"Representation of a Mopar vehicle lock."""

    def __init__(self, data, index):
        """Initialize the Mopar lock."""
        self._session = data.session
        self._index = index
        self._name = '{} Lock'.format(data.get_vehicle_name(self._index))
        self._state = None

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def is_locked(self):
        """Return true if vehicle is locked."""
        return self._state == STATE_LOCKED

    @property
    def should_poll(self):
        """Return the polling requirement for this lock."""
        return False

    def lock(self, **kwargs):
        """Lock the vehicle."""
        import motorparts

        try:
            response = motorparts.lock(self._session, self._index)
        except motorparts.MoparError as error:
            _LOGGER.error(error)
            return

        if response == SUCCESS_RESPONSE:
            self._state = STATE_LOCKED

    def unlock(self, **kwargs):
        """Unlock the vehicle."""
        import motorparts

        try:
            response = motorparts.unlock(self._session, self._index)
        except motorparts.MoparError as error:
            _LOGGER.error(error)
            return

        if response == SUCCESS_RESPONSE:
            self._state = STATE_UNLOCKED

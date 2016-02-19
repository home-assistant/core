"""
homeassistant.components.lock.verisure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with Verisure locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/verisure/
"""
import logging

import homeassistant.components.verisure as verisure
from homeassistant.components.lock import LockDevice
from homeassistant.const import STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED

_LOGGER = logging.getLogger(__name__)
ATTR_CODE = 'code'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Verisure platform. """

    if not verisure.MY_PAGES:
        _LOGGER.error('A connection has not been made to Verisure mypages.')
        return False

    locks = []

    locks.extend([VerisureDoorlock(value)
                  for value in verisure.LOCK_STATUS.values()
                  if verisure.SHOW_LOCKS])

    add_devices(locks)


# pylint: disable=abstract-method
class VerisureDoorlock(LockDevice):
    """ Represents a Verisure doorlock status. """

    def __init__(self, lock_status, code=None):
        self._id = lock_status.id
        self._state = STATE_UNKNOWN
        self._code = code

    @property
    def name(self):
        """ Returns the name of the device. """
        return 'Lock {}'.format(self._id)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def code_format(self):
        """ Six digit code required. """
        return '^\\d{%s}$' % verisure.CODE_DIGITS

    def update(self):
        """ Update lock status """
        verisure.update_lock()

        if verisure.LOCK_STATUS[self._id].status == 'unlocked':
            self._state = STATE_UNLOCKED
        elif verisure.LOCK_STATUS[self._id].status == 'locked':
            self._state = STATE_LOCKED
        elif verisure.LOCK_STATUS[self._id].status != 'pending':
            _LOGGER.error(
                'Unknown lock state %s',
                verisure.LOCK_STATUS[self._id].status)

    @property
    def is_locked(self):
        """ True if device is locked. """
        return verisure.LOCK_STATUS[self._id].status

    def unlock(self, **kwargs):
        """ Send unlock command. """
        verisure.MY_PAGES.lock.set(kwargs[ATTR_CODE], self._id, 'UNLOCKED')
        _LOGGER.info('verisure doorlock unlocking')
        verisure.MY_PAGES.lock.wait_while_pending()
        verisure.update_lock()

    def lock(self, **kwargs):
        """ Send lock command. """
        verisure.MY_PAGES.lock.set(kwargs[ATTR_CODE], self._id, 'LOCKED')
        _LOGGER.info('verisure doorlock locking')
        verisure.MY_PAGES.lock.wait_while_pending()
        verisure.update_lock()

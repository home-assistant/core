"""Tests for the Verisure platform."""

from unittest.mock import Mock, patch
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED


NO_DEFAULT_LOCK_CODE_CONFIG = {
    'locks': True,
}

DEFAULT_LOCK_CODE_CONFIG = {
    'locks': True,
    'default_lock_code': '9999',
}


async def test_verisure_no_default_code(hass):
    """Test configs without a default lock code."""
    with patch('homeassistant.components.lock.verisure.hub') as hub:
        hub.config = NO_DEFAULT_LOCK_CODE_CONFIG

        from homeassistant.components.lock.verisure import VerisureDoorlock
        lock = VerisureDoorlock("lock")
        tests = [
            {'method': lock.lock, 'state': STATE_LOCKED},
            {'method': lock.unlock, 'state': STATE_UNLOCKED},
        ]

        for test in tests:
            lock.set_lock_state = Mock(name='set_lock_state',
                                       return_value=None)

            test['method']()
            lock.set_lock_state.assert_not_called()

            test['method'](code='12345')
            lock.set_lock_state.assert_called_with('12345', test['state'])


async def test_verisure_default_code(hass):
    """Test configs with a default lock code."""
    with patch('homeassistant.components.lock.verisure.hub') as hub:
        hub.config = DEFAULT_LOCK_CODE_CONFIG

        from homeassistant.components.lock.verisure import VerisureDoorlock
        lock = VerisureDoorlock("lock")
        tests = [
            {'method': lock.lock, 'state': STATE_LOCKED},
            {'method': lock.unlock, 'state': STATE_UNLOCKED},
        ]

        for test in tests:
            lock.set_lock_state = Mock(name='set_lock_state',
                                       return_value=None)

            test['method']()
            lock.set_lock_state.assert_called_with('9999', test['state'])

            test['method'](code='12345')
            lock.set_lock_state.assert_called_with('12345', test['state'])

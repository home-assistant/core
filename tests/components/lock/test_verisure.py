"""Tests for the Verisure platform."""

from contextlib import contextmanager
from unittest.mock import Mock, patch, call
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.helpers import discovery
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN, SERVICE_LOCK, SERVICE_UNLOCK)
from homeassistant.components.verisure import DOMAIN as VERISURE_DOMAIN


NO_DEFAULT_LOCK_CODE_CONFIG = {
    'username': 'test',
    'password': 'test',
    'locks': True,
}

DEFAULT_LOCK_CODE_CONFIG = {
    'username': 'test',
    'password': 'test',
    'locks': True,
    'default_lock_code': '9999',
}

LOCKS = ['door_lock']
LOCK_CODE_TESTS = [
    {
        'service': SERVICE_LOCK,
        'start': STATE_UNLOCKED,
        'end': STATE_LOCKED,
    },
    {
        'service': SERVICE_UNLOCK,
        'start': STATE_LOCKED,
        'end': STATE_UNLOCKED,
    },
]


@contextmanager
def mock_hub(config, get_response=LOCKS[0]):
    """Extensively mock out a verisure hub."""
    hub_prefix = 'homeassistant.components.lock.verisure.hub'
    with patch(hub_prefix) as hub:
        hub.config = config
        hub.update_overview.return_value = None
        hub.get.return_value = LOCKS
        hub.get_first.return_value = get_response.upper()

        yield


async def setup_verisure_locks(hass, config):
    """Set up mock verisure locks."""
    with mock_hub(config):
        discovery.load_platform(hass, LOCK_DOMAIN, VERISURE_DOMAIN, {},
                                config)
        await hass.async_block_till_done()
        # lock.door_lock, group.all_locks
        assert len(hass.states.async_all()) == 2


async def test_verisure_no_default_code(hass):
    """Test configs without a default lock code."""
    await setup_verisure_locks(hass, NO_DEFAULT_LOCK_CODE_CONFIG)
    lock = hass.data[LOCK_DOMAIN].get_entity('lock.door_lock')
    # Don't actually update state machine
    lock.update = Mock('update', return_value=None)

    for test in LOCK_CODE_TESTS:
        with mock_hub(NO_DEFAULT_LOCK_CODE_CONFIG, test['start']):
            mock = Mock(name='set_lock_state', return_value=None)
            lock.set_lock_state = mock

            await hass.services.async_call(LOCK_DOMAIN, test['service'], {
                'entity_id': 'lock.door_lock',
            })
            await hass.async_block_till_done()
            assert mock.call_count == 0

            await hass.services.async_call(LOCK_DOMAIN, test['service'], {
                'entity_id': 'lock.door_lock',
                'code': '12345',
            })
            await hass.async_block_till_done()
            assert mock.call_args == call('12345', test['end'])


async def test_verisure_default_code(hass):
    """Test configs with a default lock code."""
    await setup_verisure_locks(hass, DEFAULT_LOCK_CODE_CONFIG)
    lock = hass.data[LOCK_DOMAIN].get_entity('lock.door_lock')
    # Don't actually update state machine
    lock.update = Mock('update', return_value=None)

    for test in LOCK_CODE_TESTS:
        with mock_hub(DEFAULT_LOCK_CODE_CONFIG, test['start']):
            mock = Mock(name='set_lock_state', return_value=None)
            lock.set_lock_state = mock

            await hass.services.async_call(LOCK_DOMAIN, test['service'], {
                'entity_id': 'lock.door_lock',
            })
            await hass.async_block_till_done()
            assert mock.call_args == call('9999', test['end'])

            await hass.services.async_call(LOCK_DOMAIN, test['service'], {
                'entity_id': 'lock.door_lock',
                'code': '12345',
            })
            await hass.async_block_till_done()
            assert mock.call_args == call('12345', test['end'])

"""Test the FreeDNS component."""
import asyncio
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import freedns
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

ACCESS_TOKEN = 'test_token'
UPDATE_INTERVAL = freedns.DEFAULT_INTERVAL
UPDATE_URL = freedns.UPDATE_URL


@pytest.fixture
def setup_freedns(hass, aioclient_mock):
    """Fixture that sets up FreeDNS."""
    params = {}
    params[ACCESS_TOKEN] = ""
    aioclient_mock.get(
        UPDATE_URL, params=params, text='Successfully updated 1 domains.')

    hass.loop.run_until_complete(async_setup_component(hass, freedns.DOMAIN, {
            freedns.DOMAIN: {
                'access_token': ACCESS_TOKEN,
                'update_interval': UPDATE_INTERVAL,
            }
        }))


@asyncio.coroutine
def test_setup(hass, aioclient_mock):
    """Test setup works if update passes."""
    params = {}
    params[ACCESS_TOKEN] = ""
    aioclient_mock.get(
        UPDATE_URL, params=params, text='ERROR: Address has not changed.')

    result = yield from async_setup_component(hass, freedns.DOMAIN, {
        freedns.DOMAIN: {
            'access_token': ACCESS_TOKEN,
            'update_interval': UPDATE_INTERVAL,
        }
    })
    assert result
    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    yield from hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


@asyncio.coroutine
def test_setup_fails_if_wrong_token(hass, aioclient_mock):
    """Test setup fails if first update fails through wrong token."""
    params = {}
    params[ACCESS_TOKEN] = ""
    aioclient_mock.get(
        UPDATE_URL, params=params, text='ERROR: Invalid update URL (2)')

    result = yield from async_setup_component(hass, freedns.DOMAIN, {
        freedns.DOMAIN: {
            'access_token': ACCESS_TOKEN,
            'update_interval': UPDATE_INTERVAL,
        }
    })
    assert not result
    assert aioclient_mock.call_count == 1

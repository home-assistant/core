"""Test the Mythic Beasts DNS component."""
import asyncio
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import mythicbeastsdns
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

DOMAIN = 'example.org'
PASSWORD = 'test_password'
HOST = 'test'
UPDATE_INTERVAL = mythicbeastsdns.DEFAULT_INTERVAL
UPDATE_URL = mythicbeastsdns.UPDATE_URL


@pytest.fixture
def setup_mythicbeastsdns(hass, aioclient_mock):
    """Fixture that sets up Mythic Beasts."""
    aioclient_mock.post(UPDATE_URL, data={
        'domain': DOMAIN,
        'password': PASSWORD,
        'command': "REPLACE {} 5 A DYNAMIC_IP".format(HOST)
    }, text='REPLACE {} 5 A DYNAMIC_IP'.format(HOST))

    hass.loop.run_until_complete(
        async_setup_component(hass, mythicbeastsdns.DOMAIN, {
            mythicbeastsdns.DOMAIN: {
                'domain': DOMAIN,
                'password': PASSWORD,
                'host': HOST,
            }
        }))


@asyncio.coroutine
def test_setup(hass, aioclient_mock):
    """Test setup works if update passes."""
    aioclient_mock.post(UPDATE_URL, data={
        'domain': DOMAIN,
        'password': PASSWORD,
        'command': "REPLACE {} 5 A DYNAMIC_IP".format(HOST)
    }, text='REPLACE {} 5 A DYNAMIC_IP'.format(HOST))

    result = yield from async_setup_component(hass, mythicbeastsdns.DOMAIN, {
        mythicbeastsdns.DOMAIN: {
            'domain': DOMAIN,
            'password': PASSWORD,
            'host': HOST
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
    aioclient_mock.post(UPDATE_URL, data={
        'domain': DOMAIN,
        'password': PASSWORD,
        'command': "REPLACE {} 5 A DYNAMIC_IP".format(HOST)
    }, text='ERR Not authenticated')

    result = yield from async_setup_component(hass, mythicbeastsdns.DOMAIN, {
        mythicbeastsdns.DOMAIN: {
            'domain': DOMAIN,
            'password': PASSWORD,
            'host': HOST,
        }
    })
    assert not result
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_setup_fails_if_invalid_host(hass, aioclient_mock):
    """Test setup fails if first update fails through wrong token."""
    aioclient_mock.post(UPDATE_URL, data={
        'domain': DOMAIN,
        'password': PASSWORD,
        'command': "REPLACE {} 5 A DYNAMIC_IP".format(HOST)
    }, text='NREPLACE test 5 A DYNAMIC_IP;Invalid host (must be "@", "*" or\
     only contain a-z, 0-9, - and .)')

    result = yield from async_setup_component(hass, mythicbeastsdns.DOMAIN, {
        mythicbeastsdns.DOMAIN: {
            'domain': DOMAIN,
            'password': PASSWORD,
            'host': HOST,
        }
    })
    assert not result
    assert aioclient_mock.call_count == 1

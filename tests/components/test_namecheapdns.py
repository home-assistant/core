"""Test the NamecheapDNS component."""
import asyncio
from datetime import timedelta

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import namecheapdns
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

HOST = 'test'
DOMAIN = 'bla'
TOKEN = 'abcdefgh'


@pytest.fixture
def setup_namecheapdns(hass, aioclient_mock):
    """Fixture that sets up NamecheapDNS."""
    aioclient_mock.get(namecheapdns.UPDATE_URL, params={
        'host': HOST,
        'domain': DOMAIN,
        'password': TOKEN
    }, text='<interface-response><ErrCount>0</ErrCount></interface-response>')

    hass.loop.run_until_complete(async_setup_component(
        hass, namecheapdns.DOMAIN, {
            'namecheapdns': {
                'host': HOST,
                'domain': DOMAIN,
                'access_token': TOKEN
            }
        }))


@asyncio.coroutine
def test_setup(hass, aioclient_mock):
    """Test setup works if update passes."""
    aioclient_mock.get(namecheapdns.UPDATE_URL, params={
        'host': HOST,
        'domain': DOMAIN,
        'password': TOKEN
    }, text='<interface-response><ErrCount>0</ErrCount></interface-response>')

    result = yield from async_setup_component(hass, namecheapdns.DOMAIN, {
        'namecheapdns': {
            'host': HOST,
            'domain': DOMAIN,
            'access_token': TOKEN
        }
    })
    assert result
    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    yield from hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


@asyncio.coroutine
def test_setup_fails_if_update_fails(hass, aioclient_mock):
    """Test setup fails if first update fails."""
    aioclient_mock.get(namecheapdns.UPDATE_URL, params={
        'host': HOST,
        'domain': DOMAIN,
        'password': TOKEN
    }, text='<interface-response><ErrCount>1</ErrCount></interface-response>')

    result = yield from async_setup_component(hass, namecheapdns.DOMAIN, {
        'namecheapdns': {
            'host': HOST,
            'domain': DOMAIN,
            'access_token': TOKEN
        }
    })
    assert not result
    assert aioclient_mock.call_count == 1

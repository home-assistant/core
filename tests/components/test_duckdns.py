"""Test the DuckDNS component."""
import asyncio
from datetime import timedelta

import pytest

from homeassistant.loader import bind_hass
from homeassistant.setup import async_setup_component
from homeassistant.components import duckdns
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

DOMAIN = 'bla'
TOKEN = 'abcdefgh'


@bind_hass
@asyncio.coroutine
def async_set_txt(hass, txt):
    """Set the txt record. Pass in None to remove it.

    This is a legacy helper method. Do not use it for new tests.
    """
    yield from hass.services.async_call(
        duckdns.DOMAIN, duckdns.SERVICE_SET_TXT, {
            duckdns.ATTR_TXT: txt
        }, blocking=True)


@pytest.fixture
def setup_duckdns(hass, aioclient_mock):
    """Fixture that sets up DuckDNS."""
    aioclient_mock.get(duckdns.UPDATE_URL, params={
        'domains': DOMAIN,
        'token': TOKEN
    }, text='OK')

    hass.loop.run_until_complete(async_setup_component(
        hass, duckdns.DOMAIN, {
            'duckdns': {
                'domain': DOMAIN,
                'access_token': TOKEN
            }
        }))


@asyncio.coroutine
def test_setup(hass, aioclient_mock):
    """Test setup works if update passes."""
    aioclient_mock.get(duckdns.UPDATE_URL, params={
        'domains': DOMAIN,
        'token': TOKEN
    }, text='OK')

    result = yield from async_setup_component(hass, duckdns.DOMAIN, {
        'duckdns': {
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
    aioclient_mock.get(duckdns.UPDATE_URL, params={
        'domains': DOMAIN,
        'token': TOKEN
    }, text='KO')

    result = yield from async_setup_component(hass, duckdns.DOMAIN, {
        'duckdns': {
            'domain': DOMAIN,
            'access_token': TOKEN
        }
    })
    assert not result
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_service_set_txt(hass, aioclient_mock, setup_duckdns):
    """Test set txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(duckdns.UPDATE_URL, params={
        'domains': DOMAIN,
        'token': TOKEN,
        'txt': 'some-txt',
    }, text='OK')

    assert aioclient_mock.call_count == 0
    yield from async_set_txt(hass, 'some-txt')
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_service_clear_txt(hass, aioclient_mock, setup_duckdns):
    """Test clear txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(duckdns.UPDATE_URL, params={
        'domains': DOMAIN,
        'token': TOKEN,
        'txt': '',
        'clear': 'true',
    }, text='OK')

    assert aioclient_mock.call_count == 0
    yield from async_set_txt(hass, None)
    assert aioclient_mock.call_count == 1

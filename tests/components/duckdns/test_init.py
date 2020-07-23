"""Test the DuckDNS component."""
from datetime import timedelta
import logging

import pytest

from homeassistant.components import duckdns
from homeassistant.components.duckdns import async_track_time_interval_backoff
from homeassistant.loader import bind_hass
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

DOMAIN = "bla"
TOKEN = "abcdefgh"
_LOGGER = logging.getLogger(__name__)
INTERVAL = duckdns.INTERVAL


@bind_hass
async def async_set_txt(hass, txt):
    """Set the txt record. Pass in None to remove it.

    This is a legacy helper method. Do not use it for new tests.
    """
    await hass.services.async_call(
        duckdns.DOMAIN, duckdns.SERVICE_SET_TXT, {duckdns.ATTR_TXT: txt}, blocking=True
    )


@pytest.fixture
def setup_duckdns(hass, aioclient_mock):
    """Fixture that sets up DuckDNS."""
    aioclient_mock.get(
        duckdns.UPDATE_URL, params={"domains": DOMAIN, "token": TOKEN}, text="OK"
    )

    hass.loop.run_until_complete(
        async_setup_component(
            hass, duckdns.DOMAIN, {"duckdns": {"domain": DOMAIN, "access_token": TOKEN}}
        )
    )


async def test_setup(hass, aioclient_mock):
    """Test setup works if update passes."""
    aioclient_mock.get(
        duckdns.UPDATE_URL, params={"domains": DOMAIN, "token": TOKEN}, text="OK"
    )

    result = await async_setup_component(
        hass, duckdns.DOMAIN, {"duckdns": {"domain": DOMAIN, "access_token": TOKEN}}
    )

    await hass.async_block_till_done()

    assert result
    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_setup_backoff(hass, aioclient_mock):
    """Test setup fails if first update fails."""
    aioclient_mock.get(
        duckdns.UPDATE_URL, params={"domains": DOMAIN, "token": TOKEN}, text="KO"
    )

    result = await async_setup_component(
        hass, duckdns.DOMAIN, {"duckdns": {"domain": DOMAIN, "access_token": TOKEN}}
    )
    assert result
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1

    # Copy of the DuckDNS intervals from duckdns/__init__.py
    intervals = (
        INTERVAL,
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(minutes=30),
    )
    tme = utcnow()
    await hass.async_block_till_done()

    _LOGGER.debug("Backoff...")
    for idx in range(1, len(intervals)):
        tme += intervals[idx]
        async_fire_time_changed(hass, tme)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == idx + 1


async def test_service_set_txt(hass, aioclient_mock, setup_duckdns):
    """Test set txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(
        duckdns.UPDATE_URL,
        params={"domains": DOMAIN, "token": TOKEN, "txt": "some-txt"},
        text="OK",
    )

    assert aioclient_mock.call_count == 0
    await async_set_txt(hass, "some-txt")
    assert aioclient_mock.call_count == 1


async def test_service_clear_txt(hass, aioclient_mock, setup_duckdns):
    """Test clear txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(
        duckdns.UPDATE_URL,
        params={"domains": DOMAIN, "token": TOKEN, "txt": "", "clear": "true"},
        text="OK",
    )

    assert aioclient_mock.call_count == 0
    await async_set_txt(hass, None)
    assert aioclient_mock.call_count == 1


async def test_async_track_time_interval_backoff(hass):
    """Test setup fails if first update fails."""
    ret_val = False
    call_count = 0
    tme = None

    async def _return(now):
        nonlocal call_count, ret_val, tme
        if tme is None:
            tme = now
        call_count += 1
        return ret_val

    intervals = (
        INTERVAL,
        INTERVAL * 2,
        INTERVAL * 5,
        INTERVAL * 9,
        INTERVAL * 10,
        INTERVAL * 11,
        INTERVAL * 12,
    )

    async_track_time_interval_backoff(hass, _return, intervals)
    await hass.async_block_till_done()

    assert call_count == 1

    _LOGGER.debug("Backoff...")
    for idx in range(1, len(intervals)):
        tme += intervals[idx]
        async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
        await hass.async_block_till_done()

        assert call_count == idx + 1

    _LOGGER.debug("Max backoff reached - intervals[-1]")
    for _idx in range(1, 10):
        tme += intervals[-1]
        async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
        await hass.async_block_till_done()

        assert call_count == idx + 1 + _idx

    _LOGGER.debug("Reset backoff")
    call_count = 0
    ret_val = True
    tme += intervals[-1]
    async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
    await hass.async_block_till_done()
    assert call_count == 1

    _LOGGER.debug("No backoff - intervals[0]")
    for _idx in range(2, 10):
        tme += intervals[0]
        async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
        await hass.async_block_till_done()

        assert call_count == _idx

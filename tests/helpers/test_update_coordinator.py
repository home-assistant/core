"""Tests for the update coordinator."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
from asynctest import CoroutineMock, Mock
import pytest

from homeassistant.helpers import update_coordinator
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

LOGGER = logging.getLogger(__name__)


@pytest.fixture
def crd(hass):
    """Coordinator mock."""
    calls = []

    async def refresh():
        calls.append(None)
        return len(calls)

    crd = update_coordinator.DataUpdateCoordinator(
        hass,
        LOGGER,
        name="test",
        update_method=refresh,
        update_interval=timedelta(seconds=10),
    )
    return crd


async def test_async_refresh(crd):
    """Test async_refresh for update coordinator."""
    assert crd.data is None
    await crd.async_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True

    updates = []

    def update_callback():
        updates.append(crd.data)

    crd.async_add_listener(update_callback)

    await crd.async_refresh()

    assert updates == [2]

    crd.async_remove_listener(update_callback)

    await crd.async_refresh()

    assert updates == [2]


async def test_request_refresh(crd):
    """Test request refresh for update coordinator."""
    assert crd.data is None
    await crd.async_request_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True

    # Second time we hit the debonuce
    await crd.async_request_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True


@pytest.mark.parametrize(
    "err_msg",
    [
        (asyncio.TimeoutError, "Timeout fetching test data"),
        (aiohttp.ClientError, "Error requesting test data"),
        (update_coordinator.UpdateFailed, "Error fetching test data"),
    ],
)
async def test_refresh_known_errors(err_msg, crd, caplog):
    """Test raising known errors."""
    crd.update_method = CoroutineMock(side_effect=err_msg[0])

    await crd.async_refresh()

    assert crd.data is None
    assert crd.last_update_success is False
    assert err_msg[1] in caplog.text


async def test_refresh_fail_unknown(crd, caplog):
    """Test raising unknown error."""
    await crd.async_refresh()

    crd.update_method = CoroutineMock(side_effect=ValueError)

    await crd.async_refresh()

    assert crd.data == 1  # value from previous fetch
    assert crd.last_update_success is False
    assert "Unexpected error fetching test data" in caplog.text


async def test_update_interval(hass, crd):
    """Test update interval works."""
    # Test we don't update without subscriber
    async_fire_time_changed(hass, utcnow() + crd.update_interval)
    await hass.async_block_till_done()
    assert crd.data is None

    # Add subscriber
    update_callback = Mock()
    crd.async_add_listener(update_callback)

    # Test twice we update with subscriber
    async_fire_time_changed(hass, utcnow() + crd.update_interval)
    await hass.async_block_till_done()
    assert crd.data == 1

    async_fire_time_changed(hass, utcnow() + crd.update_interval)
    await hass.async_block_till_done()
    assert crd.data == 2

    # Test removing listener
    crd.async_remove_listener(update_callback)

    async_fire_time_changed(hass, utcnow() + crd.update_interval)
    await hass.async_block_till_done()

    # Test we stop updating after we lose last subscriber
    assert crd.data == 2

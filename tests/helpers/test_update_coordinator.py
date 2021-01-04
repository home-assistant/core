"""Tests for the update coordinator."""
import asyncio
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, Mock, patch
import urllib.error

import aiohttp
import pytest
import requests

from homeassistant.helpers import update_coordinator
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


def get_crd(hass, update_interval):
    """Make coordinator mocks."""
    calls = 0

    async def refresh() -> int:
        nonlocal calls
        calls += 1
        return calls

    crd = update_coordinator.DataUpdateCoordinator[int](
        hass,
        _LOGGER,
        name="test",
        update_method=refresh,
        update_interval=update_interval,
    )
    return crd


DEFAULT_UPDATE_INTERVAL = timedelta(seconds=10)


@pytest.fixture
def crd(hass):
    """Coordinator mock with default update interval."""
    return get_crd(hass, DEFAULT_UPDATE_INTERVAL)


@pytest.fixture
def crd_without_update_interval(hass):
    """Coordinator mock that never automatically updates."""
    return get_crd(hass, None)


async def test_async_refresh(crd):
    """Test async_refresh for update coordinator."""
    assert crd.data is None
    await crd.async_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True
    # Make sure we didn't schedule a refresh because we have 0 listeners
    assert crd._unsub_refresh is None

    updates = []

    def update_callback():
        updates.append(crd.data)

    unsub = crd.async_add_listener(update_callback)
    await crd.async_refresh()
    assert updates == [2]
    assert crd._unsub_refresh is not None

    # Test unsubscribing through function
    unsub()
    await crd.async_refresh()
    assert updates == [2]

    # Test unsubscribing through method
    crd.async_add_listener(update_callback)
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


async def test_request_refresh_no_auto_update(crd_without_update_interval):
    """Test request refresh for update coordinator without automatic update."""
    crd = crd_without_update_interval
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
        (requests.exceptions.Timeout, "Timeout fetching test data"),
        (urllib.error.URLError("timed out"), "Timeout fetching test data"),
        (aiohttp.ClientError, "Error requesting test data"),
        (requests.exceptions.RequestException, "Error requesting test data"),
        (urllib.error.URLError("something"), "Error requesting test data"),
        (update_coordinator.UpdateFailed, "Error fetching test data"),
    ],
)
async def test_refresh_known_errors(err_msg, crd, caplog):
    """Test raising known errors."""
    crd.update_method = AsyncMock(side_effect=err_msg[0])

    await crd.async_refresh()

    assert crd.data is None
    assert crd.last_update_success is False
    assert err_msg[1] in caplog.text


async def test_refresh_fail_unknown(crd, caplog):
    """Test raising unknown error."""
    await crd.async_refresh()

    crd.update_method = AsyncMock(side_effect=ValueError)

    await crd.async_refresh()

    assert crd.data == 1  # value from previous fetch
    assert crd.last_update_success is False
    assert "Unexpected error fetching test data" in caplog.text


async def test_refresh_no_update_method(crd):
    """Test raising error is no update method is provided."""
    await crd.async_refresh()

    crd.update_method = None

    with pytest.raises(NotImplementedError):
        await crd.async_refresh()


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


async def test_update_interval_not_present(hass, crd_without_update_interval):
    """Test update never happens with no update interval."""
    crd = crd_without_update_interval
    # Test we don't update without subscriber with no update interval
    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert crd.data is None

    # Add subscriber
    update_callback = Mock()
    crd.async_add_listener(update_callback)

    # Test twice we don't update with subscriber with no update interval
    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert crd.data is None

    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert crd.data is None

    # Test removing listener
    crd.async_remove_listener(update_callback)

    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    # Test we stop don't update after we lose last subscriber
    assert crd.data is None


async def test_refresh_recover(crd, caplog):
    """Test recovery of freshing data."""
    crd.last_update_success = False

    await crd.async_refresh()

    assert crd.last_update_success is True
    assert "Fetching test data recovered" in caplog.text


async def test_coordinator_entity(crd):
    """Test the CoordinatorEntity class."""
    entity = update_coordinator.CoordinatorEntity(crd)

    assert entity.should_poll is False

    crd.last_update_success = False
    assert entity.available is False

    await entity.async_update()
    assert entity.available is True

    with patch(
        "homeassistant.helpers.entity.Entity.async_on_remove"
    ) as mock_async_on_remove:
        await entity.async_added_to_hass()

    assert mock_async_on_remove.called

    # Verify we do not update if the entity is disabled
    crd.last_update_success = False
    with patch("homeassistant.helpers.entity.Entity.enabled", False):
        await entity.async_update()
    assert entity.available is False


async def test_async_set_updated_data(crd):
    """Test async_set_updated_data for update coordinator."""
    assert crd.data is None

    with patch.object(crd._debounced_refresh, "async_cancel") as mock_cancel:
        crd.async_set_updated_data(100)

        # Test we cancel any pending refresh
        assert len(mock_cancel.mock_calls) == 1

    # Test data got updated
    assert crd.data == 100
    assert crd.last_update_success is True

    # Make sure we didn't schedule a refresh because we have 0 listeners
    assert crd._unsub_refresh is None

    updates = []

    def update_callback():
        updates.append(crd.data)

    crd.async_add_listener(update_callback)
    crd.async_set_updated_data(200)
    assert updates == [200]
    assert crd._unsub_refresh is not None

    old_refresh = crd._unsub_refresh

    crd.async_set_updated_data(300)
    # We have created a new refresh listener
    assert crd._unsub_refresh is not old_refresh

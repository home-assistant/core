"""Tests for the update coordinator."""

from datetime import datetime, timedelta
import logging
from unittest.mock import AsyncMock, Mock, patch
import urllib.error

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
import requests

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import update_coordinator
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)

KNOWN_ERRORS: list[tuple[Exception, type[Exception], str]] = [
    (TimeoutError(), TimeoutError, "Timeout fetching test data"),
    (
        requests.exceptions.Timeout(),
        requests.exceptions.Timeout,
        "Timeout fetching test data",
    ),
    (
        urllib.error.URLError("timed out"),
        urllib.error.URLError,
        "Timeout fetching test data",
    ),
    (aiohttp.ClientError(), aiohttp.ClientError, "Error requesting test data"),
    (
        requests.exceptions.RequestException(),
        requests.exceptions.RequestException,
        "Error requesting test data",
    ),
    (
        urllib.error.URLError("something"),
        urllib.error.URLError,
        "Error requesting test data",
    ),
    (
        update_coordinator.UpdateFailed(),
        update_coordinator.UpdateFailed,
        "Error fetching test data",
    ),
]


def get_crd(
    hass: HomeAssistant, update_interval: timedelta | None
) -> update_coordinator.DataUpdateCoordinator[int]:
    """Make coordinator mocks."""
    calls = 0

    async def refresh() -> int:
        nonlocal calls
        calls += 1
        return calls

    return update_coordinator.DataUpdateCoordinator[int](
        hass,
        _LOGGER,
        name="test",
        update_method=refresh,
        update_interval=update_interval,
    )


DEFAULT_UPDATE_INTERVAL = timedelta(seconds=10)


@pytest.fixture
def crd(hass: HomeAssistant) -> update_coordinator.DataUpdateCoordinator[int]:
    """Coordinator mock with default update interval."""
    return get_crd(hass, DEFAULT_UPDATE_INTERVAL)


@pytest.fixture
def crd_without_update_interval(
    hass: HomeAssistant,
) -> update_coordinator.DataUpdateCoordinator[int]:
    """Coordinator mock that never automatically updates."""
    return get_crd(hass, None)


async def test_async_refresh(
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
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


async def test_shutdown(
    hass: HomeAssistant,
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test async_shutdown for update coordinator."""
    assert crd.data is None
    await crd.async_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True
    # Make sure we didn't schedule a refresh because we have 0 listeners
    assert crd._unsub_refresh is None

    updates = []

    def update_callback():
        updates.append(crd.data)

    _ = crd.async_add_listener(update_callback)
    await crd.async_refresh()
    assert updates == [2]
    assert crd._unsub_refresh is not None

    # Test shutdown through function
    with patch.object(crd._debounced_refresh, "async_shutdown") as mock_shutdown:
        await crd.async_shutdown()

    async_fire_time_changed(hass, utcnow() + crd.update_interval)
    await hass.async_block_till_done()

    # Test we shutdown the debouncer and cleared the subscriptions
    assert len(mock_shutdown.mock_calls) == 1
    assert crd._unsub_refresh is None

    await crd.async_refresh()
    assert updates == [2]


async def test_shutdown_on_entry_unload(
    hass: HomeAssistant,
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test shutdown is requested on entry unload."""
    entry = MockConfigEntry()
    config_entries.current_entry.set(entry)

    calls = 0

    async def _refresh() -> int:
        nonlocal calls
        calls += 1
        return calls

    crd = update_coordinator.DataUpdateCoordinator[int](
        hass,
        _LOGGER,
        name="test",
        update_method=_refresh,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )

    crd.async_add_listener(lambda: None)
    assert crd._unsub_refresh is not None
    assert not crd._shutdown_requested

    await entry._async_process_on_unload(hass)

    assert crd._shutdown_requested
    assert crd._unsub_refresh is None


async def test_shutdown_on_hass_stop(
    hass: HomeAssistant,
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test shutdown can be shutdown on STOP event."""
    calls = 0

    async def _refresh() -> int:
        nonlocal calls
        calls += 1
        return calls

    crd = update_coordinator.DataUpdateCoordinator[int](
        hass,
        _LOGGER,
        name="test",
        update_method=_refresh,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )
    await crd.async_register_shutdown()

    crd.async_add_listener(lambda: None)
    assert crd._unsub_refresh is not None
    assert not crd._shutdown_requested

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert crd._shutdown_requested
    assert crd._unsub_refresh is None


async def test_update_context(
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test update contexts for the update coordinator."""
    await crd.async_refresh()
    assert not set(crd.async_contexts())

    def update_callback1():
        pass

    def update_callback2():
        pass

    unsub1 = crd.async_add_listener(update_callback1, 1)
    assert set(crd.async_contexts()) == {1}

    unsub2 = crd.async_add_listener(update_callback2, 2)
    assert set(crd.async_contexts()) == {1, 2}

    unsub1()
    assert set(crd.async_contexts()) == {2}

    unsub2()
    assert not set(crd.async_contexts())


async def test_request_refresh(
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test request refresh for update coordinator."""
    assert crd.data is None
    await crd.async_request_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True

    # Second time we hit the debonuce
    await crd.async_request_refresh()
    assert crd.data == 1
    assert crd.last_update_success is True

    # Cleanup to avoid lingering timer
    crd._unschedule_refresh()


async def test_request_refresh_no_auto_update(
    crd_without_update_interval: update_coordinator.DataUpdateCoordinator[int],
) -> None:
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

    # Cleanup to avoid lingering timer
    crd._unschedule_refresh()


@pytest.mark.parametrize(
    "err_msg",
    KNOWN_ERRORS,
)
async def test_refresh_known_errors(
    err_msg: tuple[Exception, type[Exception], str],
    crd: update_coordinator.DataUpdateCoordinator[int],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test raising known errors."""
    crd.update_method = AsyncMock(side_effect=err_msg[0])

    await crd.async_refresh()

    assert crd.data is None
    assert crd.last_update_success is False
    assert isinstance(crd.last_exception, err_msg[1])
    assert err_msg[2] in caplog.text


async def test_refresh_fail_unknown(
    crd: update_coordinator.DataUpdateCoordinator[int], caplog: pytest.LogCaptureFixture
) -> None:
    """Test raising unknown error."""
    await crd.async_refresh()

    crd.update_method = AsyncMock(side_effect=ValueError)

    await crd.async_refresh()

    assert crd.data == 1  # value from previous fetch
    assert crd.last_update_success is False
    assert "Unexpected error fetching test data" in caplog.text


async def test_refresh_no_update_method(
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test raising error is no update method is provided."""
    await crd.async_refresh()

    crd.update_method = None

    with pytest.raises(NotImplementedError):
        await crd.async_refresh()


async def test_update_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test update interval works."""
    # Test we don't update without subscriber
    freezer.tick(crd.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert crd.data is None

    # Add subscriber
    update_callback = Mock()
    unsub = crd.async_add_listener(update_callback)

    # Test twice we update with subscriber
    freezer.tick(crd.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert crd.data == 1

    freezer.tick(crd.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert crd.data == 2

    # Test removing listener
    unsub()

    freezer.tick(crd.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Test we stop updating after we lose last subscriber
    assert crd.data == 2


async def test_update_interval_not_present(
    hass: HomeAssistant,
    crd_without_update_interval: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test update never happens with no update interval."""
    crd = crd_without_update_interval
    # Test we don't update without subscriber with no update interval
    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert crd.data is None

    # Add subscriber
    update_callback = Mock()
    unsub = crd.async_add_listener(update_callback)

    # Test twice we don't update with subscriber with no update interval
    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert crd.data is None

    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert crd.data is None

    # Test removing listener
    unsub()

    async_fire_time_changed(hass, utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    # Test we stop don't update after we lose last subscriber
    assert crd.data is None


async def test_refresh_recover(
    crd: update_coordinator.DataUpdateCoordinator[int], caplog: pytest.LogCaptureFixture
) -> None:
    """Test recovery of freshing data."""
    crd.last_update_success = False

    await crd.async_refresh()

    assert crd.last_update_success is True
    assert "Fetching test data recovered" in caplog.text


async def test_coordinator_entity(
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
    """Test the CoordinatorEntity class."""
    context = object()
    entity = update_coordinator.CoordinatorEntity(crd, context)

    assert entity.should_poll is False

    crd.last_update_success = False
    assert entity.available is False

    await entity.async_update()
    assert entity.available is True

    with patch(
        "homeassistant.helpers.entity.Entity.async_on_remove"
    ) as mock_async_on_remove:
        await entity.async_added_to_hass()

    mock_async_on_remove.assert_called_once()
    _on_remove_callback = mock_async_on_remove.call_args[0][0]

    # Verify we do not update if the entity is disabled
    crd.last_update_success = False
    with patch("homeassistant.helpers.entity.Entity.enabled", False):
        await entity.async_update()
    assert entity.available is False

    assert list(crd.async_contexts()) == [context]

    # Call remove callback to cleanup debouncer and avoid lingering timer
    assert len(crd._listeners) == 1
    _on_remove_callback()
    assert len(crd._listeners) == 0


async def test_async_set_updated_data(
    crd: update_coordinator.DataUpdateCoordinator[int],
) -> None:
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

    remove_callbacks = crd.async_add_listener(update_callback)
    crd.async_set_updated_data(200)
    assert updates == [200]
    assert crd._unsub_refresh is not None

    old_refresh = crd._unsub_refresh

    crd.async_set_updated_data(300)
    # We have created a new refresh listener
    assert crd._unsub_refresh is not old_refresh

    # Remove callbacks to avoid lingering timers
    remove_callbacks()


async def test_stop_refresh_on_ha_stop(
    hass: HomeAssistant, crd: update_coordinator.DataUpdateCoordinator[int]
) -> None:
    """Test no update interval refresh when Home Assistant is stopping."""
    # Add subscriber
    update_callback = Mock()
    crd.async_add_listener(update_callback)

    update_interval = crd.update_interval

    # Test we update with subscriber
    async_fire_time_changed(hass, utcnow() + update_interval)
    await hass.async_block_till_done()
    assert crd.data == 1

    # Fire Home Assistant stop event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    hass.set_state(CoreState.stopping)
    await hass.async_block_till_done()

    # Make sure no update with subscriber after stop event
    async_fire_time_changed(hass, utcnow() + update_interval)
    await hass.async_block_till_done()
    assert crd.data == 1

    # Ensure we can still manually refresh after stop
    await crd.async_refresh()
    assert crd.data == 2

    # ...and that the manual refresh doesn't setup another scheduled refresh
    async_fire_time_changed(hass, utcnow() + update_interval)
    await hass.async_block_till_done()
    assert crd.data == 2


@pytest.mark.parametrize(
    "err_msg",
    KNOWN_ERRORS,
)
async def test_async_config_entry_first_refresh_failure(
    err_msg: tuple[Exception, type[Exception], str],
    crd: update_coordinator.DataUpdateCoordinator[int],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_config_entry_first_refresh raises ConfigEntryNotReady on failure.

    Verify we do not log the exception since raising ConfigEntryNotReady
    will be caught by config_entries.async_setup which will log it with
    a decreasing level of logging once the first message is logged.
    """
    crd.update_method = AsyncMock(side_effect=err_msg[0])

    with pytest.raises(ConfigEntryNotReady):
        await crd.async_config_entry_first_refresh()

    assert crd.last_update_success is False
    assert isinstance(crd.last_exception, err_msg[1])
    assert err_msg[2] not in caplog.text


async def test_async_config_entry_first_refresh_success(
    crd: update_coordinator.DataUpdateCoordinator[int], caplog: pytest.LogCaptureFixture
) -> None:
    """Test first refresh successfully."""
    await crd.async_config_entry_first_refresh()

    assert crd.last_update_success is True


async def test_not_schedule_refresh_if_system_option_disable_polling(
    hass: HomeAssistant,
) -> None:
    """Test we do not schedule a refresh if disable polling in config entry."""
    entry = MockConfigEntry(pref_disable_polling=True)
    config_entries.current_entry.set(entry)
    crd = get_crd(hass, DEFAULT_UPDATE_INTERVAL)
    crd.async_add_listener(lambda: None)
    assert crd._unsub_refresh is None


async def test_async_set_update_error(
    crd: update_coordinator.DataUpdateCoordinator[int], caplog: pytest.LogCaptureFixture
) -> None:
    """Test manually setting an update failure."""
    update_callback = Mock()
    remove_callbacks = crd.async_add_listener(update_callback)

    crd.async_set_update_error(aiohttp.ClientError("Client Failure #1"))
    assert crd.last_update_success is False
    assert "Client Failure #1" in caplog.text
    update_callback.assert_called_once()
    update_callback.reset_mock()

    # Additional failure does not log or change state
    crd.async_set_update_error(aiohttp.ClientError("Client Failure #2"))
    assert crd.last_update_success is False
    assert "Client Failure #2" not in caplog.text
    update_callback.assert_not_called()
    update_callback.reset_mock()

    crd.async_set_updated_data(200)
    assert crd.last_update_success is True
    update_callback.assert_called_once()
    update_callback.reset_mock()

    crd.async_set_update_error(aiohttp.ClientError("Client Failure #3"))
    assert crd.last_update_success is False
    assert "Client Failure #2" not in caplog.text
    update_callback.assert_called_once()

    # Remove callbacks to avoid lingering timers
    remove_callbacks()


async def test_only_callback_on_change_when_always_update_is_false(
    crd: update_coordinator.DataUpdateCoordinator[int], caplog: pytest.LogCaptureFixture
) -> None:
    """Test we do not callback listeners unless something has actually changed when always_update is false."""
    update_callback = Mock()
    crd.always_update = False
    remove_callbacks = crd.async_add_listener(update_callback)
    mocked_data = None
    mocked_exception = None

    async def _update_method() -> int:
        nonlocal mocked_data
        nonlocal mocked_exception
        if mocked_exception is not None:
            raise mocked_exception
        return mocked_data

    crd.update_method = _update_method

    mocked_data = {"a": 1}
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    mocked_data = {"a": 1}
    await crd.async_refresh()
    update_callback.assert_not_called()
    update_callback.reset_mock()

    mocked_data = None
    mocked_exception = aiohttp.ClientError("Client Failure #1")
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    mocked_data = None
    mocked_exception = aiohttp.ClientError("Client Failure #1")
    await crd.async_refresh()
    update_callback.assert_not_called()
    update_callback.reset_mock()

    mocked_exception = None
    mocked_data = {"a": 1}
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    mocked_data = {"a": 1}
    await crd.async_refresh()
    update_callback.assert_not_called()
    update_callback.reset_mock()

    mocked_data = {"a": 2}
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    mocked_data = {"a": 2}
    await crd.async_refresh()
    update_callback.assert_not_called()
    update_callback.reset_mock()

    mocked_data = {"a": 2, "b": 3}
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    remove_callbacks()


async def test_always_callback_when_always_update_is_true(
    crd: update_coordinator.DataUpdateCoordinator[int], caplog: pytest.LogCaptureFixture
) -> None:
    """Test we callback listeners even though the data is the same when always_update is True."""
    update_callback = Mock()
    remove_callbacks = crd.async_add_listener(update_callback)
    mocked_data = None
    mocked_exception = None

    async def _update_method() -> int:
        nonlocal mocked_data
        nonlocal mocked_exception
        if mocked_exception is not None:
            raise mocked_exception
        return mocked_data

    crd.update_method = _update_method

    mocked_data = {"a": 1}
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    mocked_data = {"a": 1}
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    # But still don't fire it if we are only getting
    # failure over and over
    mocked_data = None
    mocked_exception = aiohttp.ClientError("Client Failure #1")
    await crd.async_refresh()
    update_callback.assert_called_once()
    update_callback.reset_mock()

    mocked_data = None
    mocked_exception = aiohttp.ClientError("Client Failure #1")
    await crd.async_refresh()
    update_callback.assert_not_called()
    update_callback.reset_mock()

    remove_callbacks()


async def test_timestamp_date_update_coordinator(hass: HomeAssistant) -> None:
    """Test last_update_success_time is set before calling listeners."""
    last_update_success_times: list[datetime | None] = []

    async def refresh() -> int:
        return 1

    crd = update_coordinator.TimestampDataUpdateCoordinator[int](
        hass,
        _LOGGER,
        name="test",
        update_method=refresh,
        update_interval=timedelta(seconds=10),
    )

    @callback
    def listener():
        last_update_success_times.append(crd.last_update_success_time)

    unsub = crd.async_add_listener(listener)

    await crd.async_refresh()

    assert len(last_update_success_times) == 1
    # Ensure the time is set before the listener is called
    assert last_update_success_times != [None]

    unsub()
    await crd.async_refresh()
    assert len(last_update_success_times) == 1

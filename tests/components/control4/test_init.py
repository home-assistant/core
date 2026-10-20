"""Test Control4 integration setup and core behaviors."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import client_exceptions
from freezegun.api import FrozenDateTimeFactory
from pyControl4.error_handling import BadCredentials, BadToken
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.control4 import RefreshTokensObject, _periodic_resync
from homeassistant.components.control4.director_utils import (
    director_get_entry_variables,
    gather_entry_variables,
    to_bool,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.util import dt as dt_util

from . import setup_integration


@pytest.fixture
def platforms() -> list[Platform]:
    """No platforms needed to test core integration behavior."""
    return []


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_periodic_resync_skips_when_already_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A periodic resync tick is skipped while a previous pass is still running."""
    await setup_integration(hass, mock_config_entry)

    resync_started = asyncio.Event()
    release_resync = asyncio.Event()

    async def _slow_resync_items(hass: HomeAssistant, entry: MockConfigEntry) -> None:
        resync_started.set()
        await release_resync.wait()

    with patch(
        "homeassistant.components.control4._resync_items",
        new=AsyncMock(side_effect=_slow_resync_items),
    ) as mock_resync:
        first_tick = hass.async_create_task(
            _periodic_resync(hass, mock_config_entry, dt_util.utcnow()),
            "test first resync tick",
        )
        await resync_started.wait()

        await _periodic_resync(hass, mock_config_entry, dt_util.utcnow())
        mock_resync.assert_called_once()

        release_resync.set()
        await first_tick


@pytest.mark.usefixtures("mock_c4_account")
async def test_concurrent_bad_token_only_refreshes_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_director: MagicMock,
) -> None:
    """Concurrent BadToken hits on different items serialize and refresh once."""
    await setup_integration(hass, mock_config_entry)

    token_valid = False
    sync_count = 0
    # Forces both initial calls to hit BadToken together, not one-then-other.
    both_calls_started = asyncio.Barrier(2)

    async def _get_item_variables(item_id: int) -> list[dict]:
        nonlocal sync_count
        if token_valid:
            return []
        if sync_count < 2:
            sync_count += 1
            await both_calls_started.wait()
        raise BadToken("expired")

    async def _fake_refresh_tokens(hass: HomeAssistant, entry: MockConfigEntry) -> None:
        nonlocal token_valid
        token_valid = True

    mock_c4_director.get_item_variables = AsyncMock(side_effect=_get_item_variables)

    with patch(
        "homeassistant.components.control4.refresh_tokens",
        new=AsyncMock(side_effect=_fake_refresh_tokens),
    ) as mock_refresh:
        await asyncio.wait_for(
            asyncio.gather(
                director_get_entry_variables(hass, mock_config_entry, 100),
                director_get_entry_variables(hass, mock_config_entry, 200),
            ),
            timeout=5,
        )
        mock_refresh.assert_awaited_once()


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_scheduled_refresh_skips_when_lock_already_held(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A scheduled refresh must not race a BadToken-triggered one held by another task."""
    await setup_integration(hass, mock_config_entry)

    lock = mock_config_entry.runtime_data.token_refresh_lock
    holder_has_lock = asyncio.Event()
    release_holder = asyncio.Event()

    async def _hold_lock() -> None:
        async with lock:
            holder_has_lock.set()
            await release_holder.wait()

    holder_task = hass.async_create_task(_hold_lock(), "test lock holder")
    await holder_has_lock.wait()

    with patch(
        "homeassistant.components.control4.refresh_tokens", new=AsyncMock()
    ) as mock_refresh:
        obj = RefreshTokensObject(hass, mock_config_entry)
        await obj.refresh_tokens(dt_util.utcnow())
        mock_refresh.assert_not_called()

    release_holder.set()
    await holder_task


@pytest.mark.usefixtures("mock_c4_account")
async def test_gather_entry_variables_isolates_per_item_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_director: MagicMock,
) -> None:
    """One item's fetch failure doesn't prevent the others from loading."""
    await setup_integration(hass, mock_config_entry)

    async def _get_item_variables(item_id: int) -> list[dict]:
        if item_id == 100:
            raise TimeoutError("device unreachable")
        return [{"varName": "Level", "value": 50}]

    mock_c4_director.get_item_variables = AsyncMock(side_effect=_get_item_variables)

    result = await gather_entry_variables(hass, mock_config_entry, [100, 200, 300])

    assert result[100] == {}
    assert result[200] == {"Level": 50}
    assert result[300] == {"Level": 50}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        (" true ", True),
        ("garbage", None),
        ("", None),
        (None, None),
        (1, True),
        (0, False),
    ],
)
def test_to_bool(value: object, expected: bool | None) -> None:
    """to_bool normalizes both real booleans and Control4's string encoding."""
    assert to_bool(value) is expected


async def test_setup_bad_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_account: MagicMock,
) -> None:
    """Test setup fails with invalid credentials."""
    mock_c4_account.get_account_bearer_token.side_effect = BadCredentials(
        "Invalid credentials"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == (
        "Error authenticating with the Control4 account API, incorrect username or"
        " password"
    )


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_unload_tears_down_push_resources(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_websocket: MagicMock,
) -> None:
    """Unloading disconnects the WebSocket and cancels both scheduled callbacks."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    runtime_data = mock_config_entry.runtime_data
    cancel_refresh = MagicMock(side_effect=runtime_data.cancel_token_refresh_callback)
    cancel_resync = MagicMock(side_effect=runtime_data.cancel_periodic_resync_callback)
    runtime_data.cancel_token_refresh_callback = cancel_refresh
    runtime_data.cancel_periodic_resync_callback = cancel_resync

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_c4_websocket.sio_disconnect.assert_awaited_once()
    cancel_refresh.assert_called_once()
    cancel_resync.assert_called_once()
    assert runtime_data.cancel_periodic_resync_callback is None


@pytest.mark.parametrize(
    ("client", "method", "exception", "websocket_torn_down"),
    [
        ("account", "get_account_bearer_token", TimeoutError, False),
        ("account", "get_director_bearer_token", client_exceptions.ClientError, False),
        ("websocket", "sio_connect", ConnectionError, False),
        ("account", "get_account_controllers", TimeoutError, True),
        ("director", "get_all_item_info", client_exceptions.ClientError, True),
        ("director", "get_ui_configuration", TimeoutError, True),
    ],
)
async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_account: MagicMock,
    mock_c4_director: MagicMock,
    mock_c4_websocket: MagicMock,
    client: str,
    method: str,
    exception: type[Exception],
    websocket_torn_down: bool,
) -> None:
    """Connection failures at any setup step retry setup without leaking the WebSocket."""
    mocks = {
        "account": mock_c4_account,
        "director": mock_c4_director,
        "websocket": mock_c4_websocket,
    }
    getattr(mocks[client], method).side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_c4_websocket.sio_disconnect.await_count == int(websocket_torn_down)


@pytest.mark.usefixtures("mock_c4_director")
async def test_setup_retry_reuses_websocket(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_c4_account: MagicMock,
    mock_c4_websocket: MagicMock,
) -> None:
    """A retried setup reuses the WebSocket created by the failed attempt."""
    mock_c4_account.get_account_controllers.side_effect = TimeoutError
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_c4_account.get_account_controllers.side_effect = None
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.websocket is mock_c4_websocket
    assert mock_c4_websocket.sio_connect.await_count == 2


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_token_refresh_retries_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed background token refresh schedules a backoff retry."""
    await setup_integration(hass, mock_config_entry)

    obj = RefreshTokensObject(hass, mock_config_entry)
    with patch(
        "homeassistant.components.control4.refresh_tokens",
        new=AsyncMock(side_effect=ConfigEntryNotReady),
    ):
        await obj.refresh_tokens(dt_util.utcnow())

    assert obj.retries == 1
    assert mock_config_entry.runtime_data.cancel_token_refresh_callback is not None


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_token_refresh_bad_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Bad credentials during a background token refresh are logged, not retried."""
    await setup_integration(hass, mock_config_entry)

    obj = RefreshTokensObject(hass, mock_config_entry)
    with patch(
        "homeassistant.components.control4.refresh_tokens",
        new=AsyncMock(side_effect=ConfigEntryError),
    ):
        await obj.refresh_tokens(dt_util.utcnow())

    assert obj.retries == 0
    assert "Control4 credentials are no longer valid" in caplog.text

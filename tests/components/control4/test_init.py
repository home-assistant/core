"""Test Control4 integration setup and core behaviors."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pyControl4.error_handling import BadToken
import pytest

from homeassistant.components.control4 import RefreshTokensObject, _periodic_resync
from homeassistant.components.control4.director_utils import (
    director_get_entry_variables,
    gather_entry_variables,
    to_bool,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry


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

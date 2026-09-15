"""Test Control4 integration setup and core behaviors."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from pyControl4.error_handling import BadToken
import pytest

from homeassistant.components.control4.const import WEBSOCKET_RESYNC_INTERVAL_SEC
from homeassistant.components.control4.director_utils import (
    director_get_entry_variables,
    to_bool,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


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

    with patch(
        "homeassistant.components.control4._resync_items", new=AsyncMock()
    ) as mock_resync:
        async with mock_config_entry.runtime_data.resync_lock:
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + timedelta(seconds=WEBSOCKET_RESYNC_INTERVAL_SEC),
            )
            await hass.async_block_till_done()
        mock_resync.assert_not_called()


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

"""Test setup cancellation and controller cleanup."""

import asyncio
from unittest.mock import MagicMock, call, patch

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(
            "homeassistant.components.terrestream_local.Client.return_value.refresh",
            id="first-refresh",
        ),
        pytest.param(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            id="platform-setup",
        ),
    ],
)
async def test_setup_cancellation_releases_lease(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    target: str,
) -> None:
    """Release ownership without swallowing cancellation during setup."""
    started = asyncio.Event()

    async def block_setup(*args: object) -> None:
        started.set()
        await asyncio.Future()

    with patch(target, side_effect=block_setup):
        task = hass.async_create_task(
            hass.config_entries.async_setup(config_entry.entry_id)
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert task.cancelled()
    mock_client.command.assert_any_await("release")
    assert mock_client.command.await_args == call("release")
    assert not hass.states.async_all("sensor")

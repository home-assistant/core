"""Test Terrestream setup and controller lease cleanup."""

import asyncio
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from terrestream_local.errors import AuthenticationError, ClientError
from terrestream_local.models import Snapshot

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant


async def test_pending_pairing(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Finish a pairing whose confirmation was interrupted."""
    mock_client.identity.return_value = {"paired": False}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.confirm.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(AuthenticationError("revoked"), id="revoked"),
        pytest.param(ClientError("offline"), id="offline"),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: Exception,
) -> None:
    """Never expose measurements from an unauthenticated endpoint."""
    mock_client.identity.side_effect = error
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert not hass.states.async_all("sensor")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ClientError("offline"), id="offline"),
        pytest.param(AuthenticationError("revoked"), id="revoked"),
    ],
)
async def test_failed_first_refresh_releases_lease(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: ClientError,
) -> None:
    """A failed setup does not leave a live lease behind."""
    mock_client.refresh.side_effect = error
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    mock_client.command.assert_any_await("release")


async def test_shutdown_release(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Graceful shutdown releases ownership before the next HA starts."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_client.command.assert_any_await("release")


@pytest.mark.parametrize(
    "release_error",
    [
        pytest.param(None, id="release-succeeds"),
        pytest.param(ClientError("offline"), id="release-fails"),
    ],
)
async def test_unload_releases_lease(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    release_error: ClientError | None,
) -> None:
    """Unload the sensors even if the device cannot acknowledge lease release."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    mock_client.command.reset_mock()
    mock_client.command.side_effect = release_error

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client.command.assert_awaited_once_with("release")
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_waits_for_in_flight_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stop an active library refresh before sending the release command."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    refresh_started = asyncio.Event()
    snapshot: Snapshot = mock_client.refresh.return_value
    events: list[str] = []

    async def blocked_refresh() -> Snapshot:
        refresh_started.set()
        try:
            await asyncio.Future()
        finally:
            events.append("refresh stopped")
        return snapshot

    async def command(name: str) -> dict[str, bool]:
        events.append(name)
        return {"ok": True}

    mock_client.refresh.side_effect = blocked_refresh
    mock_client.command.side_effect = command
    freezer.tick(31)
    async_fire_time_changed(hass)
    await refresh_started.wait()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert events == ["refresh stopped", "release"]
    mock_client.command.assert_awaited_once_with("release")
    assert config_entry.state is ConfigEntryState.NOT_LOADED

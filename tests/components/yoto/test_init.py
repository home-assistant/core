"""Tests for the Yoto integration setup."""

from unittest.mock import MagicMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from yoto_api import AuthenticationError, YotoAPIError, YotoError

from homeassistant.components.yoto.const import (
    DOMAIN,
    SCAN_INTERVAL,
    STATUS_PUSH_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_unload(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """The integration loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_yoto_client.disconnect_events.assert_called_once()


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """An authentication error during refresh triggers reauth."""
    mock_yoto_client.refresh.side_effect = AuthenticationError("denied")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    assert any(
        flow["context"].get("source") == SOURCE_REAUTH
        and flow["context"].get("entry_id") == mock_config_entry.entry_id
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_setup_update_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """A non-auth API failure surfaces as a setup retry."""
    mock_yoto_client.refresh.side_effect = YotoAPIError("boom")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mqtt_event_dispatches_update(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """An MQTT event published by the broker pushes fresh data to listeners."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is mock_yoto_client.players

    received: list[dict | None] = []
    coordinator.async_add_listener(lambda: received.append(coordinator.data))

    # connect_events(device_ids, on_update, on_disconnect) — pull the callback out
    callback = mock_yoto_client.connect_events.call_args.args[1]
    callback(next(iter(mock_yoto_client.players.values())))
    await hass.async_block_till_done()

    assert received == [mock_yoto_client.players]


async def test_status_push_tick(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The status-push timer publishes a request every 60 s."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.request_status_push.reset_mock()

    freezer.tick(STATUS_PUSH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_yoto_client.request_status_push.assert_called_once_with("player-test")


async def test_status_push_swallows_errors(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Status-push errors don't break the entry."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.request_status_push.side_effect = YotoError("boom")

    freezer.tick(STATUS_PUSH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_periodic_refresh(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The coordinator refreshes player list + status on every tick."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.refresh.reset_mock()
    mock_yoto_client.update_player_status.reset_mock()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_yoto_client.refresh.assert_called_once()
    mock_yoto_client.update_player_status.assert_called_once_with("player-test")


async def test_periodic_refresh_auth_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An auth failure mid-session triggers reauth."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.refresh.side_effect = AuthenticationError("denied")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert any(
        flow["context"].get("source") == SOURCE_REAUTH
        and flow["context"].get("entry_id") == mock_config_entry.entry_id
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_mqtt_disconnect_logs(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An MQTT disconnect with an error logs at debug level."""
    await setup_integration(hass, mock_config_entry)

    # connect_events(device_ids, on_update, on_disconnect) — pull the disconnect cb
    on_disconnect = mock_yoto_client.connect_events.call_args.args[2]
    with caplog.at_level("DEBUG", logger="homeassistant.components.yoto"):
        on_disconnect(YotoError("connection reset"))

    assert "MQTT disconnect: connection reset" in caplog.text
    # A clean shutdown (err=None) is silent.
    caplog.clear()
    on_disconnect(None)
    assert "MQTT disconnect" not in caplog.text


async def test_setup_implementation_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Missing OAuth2 implementation defers setup as not-ready."""
    with patch(
        "homeassistant.components.yoto.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError("gone"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_token_refresh_network_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """A network error while validating the token defers setup."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=aiohttp.ClientError("boom"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_library_failure_is_best_effort(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure loading the card library logs a warning but doesn't block."""
    mock_yoto_client.update_library.side_effect = YotoError("no library")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Could not load Yoto card library" in caplog.text


async def test_setup_connect_events_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """MQTT connect failure surfaces as a setup retry."""
    mock_yoto_client.connect_events.side_effect = YotoError("mqtt down")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_periodic_refresh_network_error(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A network error during periodic refresh marks the coordinator failed."""
    await setup_integration(hass, mock_config_entry)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=aiohttp.ClientError("boom"),
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is False


async def test_periodic_refresh_api_error(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A non-auth API error during periodic refresh marks the coordinator failed."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.refresh.side_effect = YotoAPIError("boom")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is False


async def test_status_per_device_failure_is_logged(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A per-device status fetch failure logs a warning and doesn't break setup."""
    mock_yoto_client.update_player_status.side_effect = YotoError("offline")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Could not refresh Yoto player" in caplog.text

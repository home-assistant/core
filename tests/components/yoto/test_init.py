"""Tests for the Yoto integration setup."""

from unittest.mock import MagicMock

from yoto_api import AuthenticationError, YotoAPIError

from homeassistant.components.yoto.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_unload(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """The integration loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_yoto_manager.disconnect.assert_called_once()


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """An authentication error during refresh triggers reauth."""
    mock_yoto_manager.update_player_list.side_effect = AuthenticationError("denied")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    assert any(
        flow["context"].get("source") == SOURCE_REAUTH
        and flow["context"].get("entry_id") == mock_config_entry.entry_id
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_setup_update_failure(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """A non-auth API failure surfaces as a setup retry."""
    mock_yoto_manager.update_player_list.side_effect = YotoAPIError("boom")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mqtt_event_dispatches_update(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """An MQTT event published by the broker pushes fresh data to listeners."""
    mock_yoto_manager.mqtt_client = None

    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is mock_yoto_manager.players

    received: list[dict | None] = []
    coordinator.async_add_listener(lambda: received.append(coordinator.data))

    callback = mock_yoto_manager.connect_to_events.call_args.args[0]
    callback()
    await hass.async_block_till_done()

    assert received == [mock_yoto_manager.players]

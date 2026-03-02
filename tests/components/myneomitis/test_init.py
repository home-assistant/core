"""Tests for the MyNeomitis integration."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from homeassistant.components.myneomitis import process_connection_update
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_minimal_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test the minimal setup of the MyNeomitis integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_raises_on_login_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that async_setup_entry sets entry to retry if login fails."""
    mock_pyaxenco_client.login.side_effect = TimeoutError("fail-login")

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that unloading via hass.config_entries.async_unload disconnects cleanly."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_pyaxenco_client.disconnect_websocket.assert_awaited_once()


async def test_unload_entry_logs_on_disconnect_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """When disconnecting the websocket fails, an error is logged."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_pyaxenco_client.disconnect_websocket.side_effect = TimeoutError("to")

    caplog.set_level("ERROR")
    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert result is True
    assert "Error while disconnecting WebSocket" in caplog.text


async def test_homeassistant_stop_disconnects_websocket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that WebSocket is disconnected on Home Assistant stop event."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_pyaxenco_client.disconnect_websocket.assert_awaited_once()


async def test_homeassistant_stop_logs_on_disconnect_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that WebSocket disconnect errors are logged on HA stop."""
    mock_pyaxenco_client.disconnect_websocket.side_effect = TimeoutError(
        "disconnect failed"
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    caplog.set_level("ERROR")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert "Error while disconnecting WebSocket" in caplog.text


async def test_setup_entry_raises_auth_failed_on_401(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """A 401 ClientResponseError from login raises ConfigEntryAuthFailed."""
    err = aiohttp.ClientResponseError(MagicMock(), (), status=401)
    mock_pyaxenco_client.login.side_effect = err

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_pyaxenco_client.disconnect_websocket.assert_not_awaited()


async def test_setup_entry_notready_on_non_401_connected_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """A non-401 ClientResponseError before WebSocket is connected → ConfigEntryNotReady."""
    err = aiohttp.ClientResponseError(MagicMock(), (), status=500)
    mock_pyaxenco_client.login.side_effect = err

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_pyaxenco_client.disconnect_websocket.assert_not_awaited()


async def test_setup_entry_client_error_after_connect_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """ClientResponseError after WebSocket is connected calls disconnect_websocket."""
    err = aiohttp.ClientResponseError(MagicMock(), (), status=503)
    mock_pyaxenco_client.get_devices.side_effect = err

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_pyaxenco_client.disconnect_websocket.assert_awaited_once()


async def test_setup_entry_client_error_after_connect_disconnect_also_fails(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """When both get_devices and disconnect_websocket fail, error is logged."""
    err = aiohttp.ClientResponseError(MagicMock(), (), status=503)
    mock_pyaxenco_client.get_devices.side_effect = err
    mock_pyaxenco_client.disconnect_websocket.side_effect = TimeoutError("disc")

    mock_config_entry.add_to_hass(hass)
    caplog.set_level("ERROR")
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Error while disconnecting WebSocket" in caplog.text


async def test_setup_entry_401_after_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """A 401 after WebSocket is connected disconnects and raises ConfigEntryAuthFailed."""
    err = aiohttp.ClientResponseError(MagicMock(), (), status=401)
    mock_pyaxenco_client.get_devices.side_effect = err

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_pyaxenco_client.disconnect_websocket.assert_awaited_once()


async def test_setup_entry_timeout_after_connect_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """TimeoutError after WebSocket is connected calls disconnect_websocket."""
    mock_pyaxenco_client.get_devices.side_effect = TimeoutError("timeout")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_pyaxenco_client.disconnect_websocket.assert_awaited_once()


async def test_setup_entry_timeout_after_connect_disconnect_also_fails(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """When get_devices times out and disconnect also fails, error is logged."""
    mock_pyaxenco_client.get_devices.side_effect = TimeoutError("t")
    mock_pyaxenco_client.disconnect_websocket.side_effect = ConnectionError("c")

    mock_config_entry.add_to_hass(hass)
    caplog.set_level("ERROR")
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Error while disconnecting WebSocket" in caplog.text


def test_process_connection_update_none_on_empty_state() -> None:
    """Empty dict returns None (no connected key)."""
    assert process_connection_update({}) is None


def test_process_connection_update_none_when_no_connected_key() -> None:
    """Dict without 'connected' key returns None."""
    assert process_connection_update({"temperature": 21.0}) is None


def test_process_connection_update_true_when_connected() -> None:
    """Returns True when connected is truthy."""
    assert process_connection_update({"connected": True}) is True


def test_process_connection_update_false_when_disconnected() -> None:
    """Returns False when connected is falsy."""
    assert process_connection_update({"connected": False}) is False

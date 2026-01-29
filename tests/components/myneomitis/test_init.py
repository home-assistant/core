"""Tests for the MyNeomitis integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.myneomitis import MyNeomitisRuntimeData, async_setup_entry
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

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        mock_api = mock_pyaxenco_client
        mock_api.login = AsyncMock()
        mock_api.connect_websocket = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.disconnect_websocket = AsyncMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_raises_on_login_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that async_setup_entry sets entry to retry if login fails."""
    mock_pyaxenco_client.login = AsyncMock(side_effect=TimeoutError("fail-login"))

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that unloading via hass.config_entries.async_unload disconnects cleanly."""
    entry = mock_config_entry
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.myneomitis.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    api = AsyncMock()
    entry.runtime_data = MyNeomitisRuntimeData(api=api, devices=[])

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True
    api.disconnect_websocket.assert_awaited_once()


async def test_unload_entry_logs_on_disconnect_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When disconnecting the websocket fails, an error is logged."""
    entry = mock_config_entry
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.myneomitis.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    api = AsyncMock()
    api.disconnect_websocket = AsyncMock(side_effect=TimeoutError("to"))
    entry.runtime_data = MyNeomitisRuntimeData(api=api, devices=[])
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    caplog.set_level("ERROR")
    result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True
    assert "Error while disconnecting WebSocket" in caplog.text


async def test_homeassistant_stop_disconnects_websocket(
    hass: HomeAssistant, mock_pyaxenco_client: AsyncMock
) -> None:
    """Test that WebSocket is disconnected on Home Assistant stop event."""

    entry = MockConfigEntry(
        domain="myneomitis", data={"email": "u@d.e", "password": "pw"}
    )

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        api = mock_pyaxenco_client
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[])
        api.disconnect_websocket = AsyncMock()

        await async_setup_entry(hass, entry)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

        api.disconnect_websocket.assert_awaited_once()


async def test_homeassistant_stop_logs_on_disconnect_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that WebSocket disconnect errors are logged on HA stop."""

    entry = MockConfigEntry(
        domain="myneomitis", data={"email": "u@d.e", "password": "pw"}
    )

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        api = mock_pyaxenco_client
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[])
        api.disconnect_websocket = AsyncMock(
            side_effect=TimeoutError("disconnect failed")
        )

        await async_setup_entry(hass, entry)

        caplog.set_level("ERROR")

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

        assert "Error while disconnecting WebSocket" in caplog.text

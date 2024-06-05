"""Test the IKEA Idasen Desk init."""

import asyncio
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

from bleak.exc import BleakError
from idasen_ha.errors import AuthFailedError
import pytest

from homeassistant.components.idasen_desk.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_and_shutdown(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
) -> None:
    """Test setup."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_desk_api.connect.assert_called_once()
    mock_desk_api.is_connected = True

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_desk_api.disconnect.assert_called_once()


@pytest.mark.parametrize("exception", [AuthFailedError(), TimeoutError(), BleakError()])
async def test_setup_connect_exception(
    hass: HomeAssistant, mock_desk_api: MagicMock, exception: Exception
) -> None:
    """Test setup with an connection exception."""
    mock_desk_api.connect = AsyncMock(side_effect=exception)
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_no_ble_device(hass: HomeAssistant, mock_desk_api: MagicMock) -> None:
    """Test setup with no BLEDevice from address."""
    with mock.patch(
        "homeassistant.components.idasen_desk.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        entry = await init_integration(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_reconnect_on_bluetooth_callback(
    hass: HomeAssistant, mock_desk_api: MagicMock
) -> None:
    """Test that a reconnect is made after the bluetooth callback is triggered."""
    with mock.patch(
        "homeassistant.components.idasen_desk.bluetooth.async_register_callback"
    ) as mock_register_callback:
        await init_integration(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        mock_desk_api.connect.assert_called_once()
        mock_register_callback.assert_called_once()

        mock_desk_api.is_connected = False
        _, register_callback_args, _ = mock_register_callback.mock_calls[0]
        bt_callback = register_callback_args[1]
        bt_callback(None, None)
        await hass.async_block_till_done()
        assert mock_desk_api.connect.call_count == 2


async def test_duplicated_disconnect_is_no_op(
    hass: HomeAssistant, mock_desk_api: MagicMock
) -> None:
    """Test that calling disconnect while disconnecting is a no-op."""
    await init_integration(hass)

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test_disconnect"}, blocking=True
    )
    await hass.async_block_till_done()

    async def mock_disconnect():
        await asyncio.sleep(0)

    mock_desk_api.disconnect.reset_mock()
    mock_desk_api.disconnect.side_effect = mock_disconnect

    # Since the disconnect button was pressed but the desk indicates "connected",
    # any update event will call disconnect()
    mock_desk_api.is_connected = True
    mock_desk_api.trigger_update_callback(None)
    mock_desk_api.trigger_update_callback(None)
    mock_desk_api.trigger_update_callback(None)
    await hass.async_block_till_done()
    mock_desk_api.disconnect.assert_called_once()


async def test_ensure_connection_state(
    hass: HomeAssistant, mock_desk_api: MagicMock
) -> None:
    """Test that the connection state is ensured."""
    await init_integration(hass)

    mock_desk_api.connect.reset_mock()
    mock_desk_api.is_connected = False
    mock_desk_api.trigger_update_callback(None)
    await hass.async_block_till_done()
    mock_desk_api.connect.assert_called_once()

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test_disconnect"}, blocking=True
    )
    await hass.async_block_till_done()

    mock_desk_api.disconnect.reset_mock()
    mock_desk_api.is_connected = True
    mock_desk_api.trigger_update_callback(None)
    await hass.async_block_till_done()
    mock_desk_api.disconnect.assert_called_once()


async def test_unload_entry(hass: HomeAssistant, mock_desk_api: MagicMock) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_desk_api.connect.assert_called_once()
    mock_desk_api.is_connected = True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_desk_api.disconnect.assert_called_once()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

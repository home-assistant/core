"""Test the IKEA Idasen Desk init."""

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

        _, register_callback_args, _ = mock_register_callback.mock_calls[0]
        bt_callback = register_callback_args[1]

        mock_desk_api.connect.reset_mock()
        bt_callback(None, None)
        await hass.async_block_till_done()
        mock_desk_api.connect.assert_called_once()

        mock_desk_api.connect.reset_mock()
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.test_disconnect"}, blocking=True
        )
        bt_callback(None, None)
        await hass.async_block_till_done()
        assert mock_desk_api.connect.call_count == 0


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

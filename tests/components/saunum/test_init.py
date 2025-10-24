"""Test Saunum Leil integration setup and teardown."""

from unittest.mock import AsyncMock, patch

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.saunum import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    mock_setup_platforms,
) -> None:
    """Test integration setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.PLATFORMS", [Platform.SENSOR, Platform.SWITCH]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    mock_setup_platforms.assert_called_once()


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
    mock_setup_platforms,
) -> None:
    """Test integration unload."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.saunum.PLATFORMS",
            [Platform.SENSOR, Platform.SWITCH],
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms"
        ) as mock_unload,
    ):
        mock_unload.return_value = True

        # Setup first
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Then unload
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_unload.assert_called_once()


async def test_async_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration setup fails when connection cannot be established."""
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.connected = False  # Simulate connection failure

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_async_setup_entry_modbus_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration setup fails when ModbusException is raised."""
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock(side_effect=ModbusException("Connection error"))

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)

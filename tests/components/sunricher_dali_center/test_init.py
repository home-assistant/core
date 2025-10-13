"""Test the Dali Center integration initialization."""

from unittest.mock import MagicMock

from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dali_gateway: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)
    mock_dali_gateway.connect.return_value = None

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_dali_gateway.connect.assert_called_once()

    assert mock_config_entry.runtime_data is not None
    assert hasattr(mock_config_entry.runtime_data, "gateway")


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dali_gateway: MagicMock,
) -> None:
    """Test setup fails when gateway connection fails."""
    mock_config_entry.add_to_hass(hass)
    mock_dali_gateway.connect.side_effect = DaliGatewayError("Connection failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_dali_gateway.connect.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dali_gateway: MagicMock,
) -> None:
    """Test successful unloading of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    loaded_state = mock_config_entry.state
    assert loaded_state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_state = mock_config_entry.state
    assert unloaded_state == ConfigEntryState.NOT_LOADED

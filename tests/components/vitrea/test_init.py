"""Test the vitrea integration setup and unloading."""

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)
    with patch("vitreaclient.client.VitreaClient", return_value=mock_vitrea_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_vitrea_client.connect.assert_called_once()


async def test_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test setup fails when connection fails."""
    mock_config_entry.add_to_hass(hass)
    mock_vitrea_client.connect.side_effect = ConnectionError("Connection failed")
    with patch("vitreaclient.client.VitreaClient", return_value=mock_vitrea_client):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    # ConnectionError raises ConfigEntryNotReady, which results in SETUP_RETRY (correct behavior)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful unloading of config entry."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_reload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test successful reloading of config entry."""
    assert init_integration.state is ConfigEntryState.LOADED
    with patch("vitreaclient.client.VitreaClient", return_value=mock_vitrea_client):
        assert await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.LOADED

"""Test Autoskope integration setup."""

from unittest.mock import AsyncMock, patch

from autoskope_client.models import CannotConnect, InvalidAuth

from homeassistant.components.autoskope import PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of entry."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.autoskope.AutoskopeApi") as mock_api_class:
        mock_api_instance = AsyncMock()
        mock_api_instance.connect.return_value = None
        mock_api_instance.close.return_value = None
        mock_api_instance.get_vehicles.return_value = []  # Return list
        mock_api_class.return_value = mock_api_instance

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Verify API was created with correct parameters
        mock_api_class.assert_called_once_with(
            host=mock_config_entry.data[CONF_HOST],
            username=mock_config_entry.data[CONF_USERNAME],
            password=mock_config_entry.data[CONF_PASSWORD],
        )

        # Verify connect was called
        mock_api_instance.connect.assert_called_once()


async def test_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with authentication failure."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.autoskope.AutoskopeApi") as mock_api_class:
        mock_api_instance = AsyncMock()
        mock_api_instance.connect.side_effect = InvalidAuth("Invalid credentials")
        mock_api_class.return_value = mock_api_instance

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        # Auth failures cause SETUP_ERROR (ConfigEntryError) until reauth flow is implemented
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.autoskope.AutoskopeApi") as mock_api_class:
        mock_api_instance = AsyncMock()
        mock_api_instance.connect.side_effect = CannotConnect("Connection failed")
        mock_api_class.return_value = mock_api_instance

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


# test_setup_entry_unexpected_error removed - bare exceptions no longer caught in async_setup_entry


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading an entry."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.autoskope.AutoskopeApi") as mock_api_class:
        mock_api_instance = AsyncMock()
        mock_api_instance.connect.return_value = None
        mock_api_instance.close.return_value = None
        mock_api_instance.get_vehicles.return_value = []  # Return list
        mock_api_class.return_value = mock_api_instance

        # Setup entry
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Unload entry
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_platforms_defined() -> None:
    """Test that platforms are properly defined."""
    assert PLATFORMS == [Platform.DEVICE_TRACKER]
    assert len(PLATFORMS) == 1

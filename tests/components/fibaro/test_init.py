"""Test init methods."""

from unittest.mock import Mock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import init_integration

from tests.common import MockConfigEntry


async def test_unload_integration(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
) -> None:
    """Test unload integration stops state listener."""
    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        await init_integration(hass, mock_config_entry)
        # Act
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Assert
        assert mock_fibaro_client.unregister_update_handler.call_count == 1

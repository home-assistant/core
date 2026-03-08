"""Test the Fibaro event platform."""

from unittest.mock import Mock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry


async def test_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_button_device: Mock,
    mock_room: Mock,
) -> None:
    """Test that the button device creates an entity."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_button_device]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.EVENT]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        entry = entity_registry.async_get("event.room_1_test_button_8_button_1")
        assert entry
        assert entry.unique_id == "hc2_111111.8.1"
        assert entry.original_name == "Room 1 Test button Button 1"

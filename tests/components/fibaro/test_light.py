"""Test the Fibaro light platform."""

from unittest.mock import Mock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry


async def test_light_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
) -> None:
    """Test that the light creates an entity."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        entry = entity_registry.async_get("light.room_1_test_light_3")
        assert entry
        assert entry.unique_id == "hc2_111111.3"
        assert entry.original_name == "Room 1 Test light"


async def test_light_brightness(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_light: Mock,
    mock_room: Mock,
) -> None:
    """Test that the light brightness value is translated."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_light]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.LIGHT]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        state = hass.states.get("light.room_1_test_light_3")
        assert state.attributes["brightness"] == 51
        assert state.state == "on"

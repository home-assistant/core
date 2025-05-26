"""Test the Fibaro cover platform."""

from unittest.mock import Mock, patch

from homeassistant.components.cover import CoverState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry


async def test_cover_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover creates an entity."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        entry = entity_registry.async_get("cover.room_1_test_cover_3")
        assert entry
        assert entry.unique_id == "hc2_111111.3"
        assert entry.original_name == "Room 1 Test cover"


async def test_cover_opening(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover opening state is reported."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        assert hass.states.get("cover.room_1_test_cover_3").state == CoverState.OPENING


async def test_cover_opening_closing_none(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover opening closing states return None if not available."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_cover.state.has_value = False
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        assert hass.states.get("cover.room_1_test_cover_3").state == CoverState.OPEN


async def test_cover_closing(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover closing state is reported."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_cover.state.str_value.return_value = "closing"
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        assert hass.states.get("cover.room_1_test_cover_3").state == CoverState.CLOSING

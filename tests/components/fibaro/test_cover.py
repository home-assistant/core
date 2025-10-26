"""Test the Fibaro cover platform."""

from unittest.mock import Mock, patch

from homeassistant.components.cover import CoverEntityFeature, CoverState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry


async def test_positionable_cover_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_positionable_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover creates an entity."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_positionable_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        entry = entity_registry.async_get("cover.room_1_test_cover_3")
        assert entry
        assert entry.supported_features == (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        assert entry.unique_id == "hc2_111111.3"
        assert entry.original_name == "Room 1 Test cover"


async def test_cover_opening(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_positionable_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover opening state is reported."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_positionable_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        assert hass.states.get("cover.room_1_test_cover_3").state == CoverState.OPENING


async def test_cover_opening_closing_none(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_positionable_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover opening closing states return None if not available."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_positionable_cover.state.str_value.return_value = ""
    mock_fibaro_client.read_devices.return_value = [mock_positionable_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        assert hass.states.get("cover.room_1_test_cover_3").state == CoverState.OPEN


async def test_cover_closing(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_positionable_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that the cover closing state is reported."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_positionable_cover.state.str_value.return_value = "closing"
    mock_fibaro_client.read_devices.return_value = [mock_positionable_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        assert hass.states.get("cover.room_1_test_cover_3").state == CoverState.CLOSING


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
        entry = entity_registry.async_get("cover.room_1_test_cover_4")
        assert entry
        assert entry.supported_features == (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
        )
        assert entry.unique_id == "hc2_111111.4"
        assert entry.original_name == "Room 1 Test cover"


async def test_cover_open_action(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that open_cover works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": "cover.room_1_test_cover_4"},
            blocking=True,
        )

        # Assert
        mock_cover.execute_action.assert_called_once_with("open", ())


async def test_cover_close_action(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that close_cover works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "cover",
            "close_cover",
            {"entity_id": "cover.room_1_test_cover_4"},
            blocking=True,
        )

        # Assert
        mock_cover.execute_action.assert_called_once_with("close", ())


async def test_cover_stop_action(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that stop_cover works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "cover",
            "stop_cover",
            {"entity_id": "cover.room_1_test_cover_4"},
            blocking=True,
        )

        # Assert
        mock_cover.execute_action.assert_called_once_with("stop", ())


async def test_cover_open_slats_action(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that open_cover_tilt works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "cover",
            "open_cover_tilt",
            {"entity_id": "cover.room_1_test_cover_4"},
            blocking=True,
        )

        # Assert
        mock_cover.execute_action.assert_called_once_with("rotateSlatsUp", ())


async def test_cover_close_tilt_action(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that close_cover_tilt works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "cover",
            "close_cover_tilt",
            {"entity_id": "cover.room_1_test_cover_4"},
            blocking=True,
        )

        # Assert
        mock_cover.execute_action.assert_called_once_with("rotateSlatsDown", ())


async def test_cover_stop_slats_action(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_cover: Mock,
    mock_room: Mock,
) -> None:
    """Test that stop_cover_tilt works."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_cover]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.COVER]):
        # Act
        await init_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "cover",
            "stop_cover_tilt",
            {"entity_id": "cover.room_1_test_cover_4"},
            blocking=True,
        )

        # Assert
        mock_cover.execute_action.assert_called_once_with("stopSlats", ())

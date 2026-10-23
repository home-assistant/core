"""Test the Fibaro switch platform."""

from unittest.mock import Mock, patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration


async def test_switch_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_switch: Mock,
    mock_room: Mock,
) -> None:
    """Test that the switch creates an entity."""

    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_switch]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.SWITCH]):
        # Act
        await init_integration(hass, mock_config_entry)
        # Assert
        entry = entity_registry.async_get("switch.room_1_test_switch_9")
        assert entry
        assert entry.unique_id == "hc2_111111.9"
        assert entry.original_name == "Room 1 Test switch"


async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_switch: Mock,
    mock_room: Mock,
) -> None:
    """Test activate scene is called."""
    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_switch]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_config_entry)
        # Act
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.room_1_test_switch_9"},
            blocking=True,
        )
        # Assert
        assert mock_switch.execute_action.call_count == 1


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_fibaro_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_switch: Mock,
    mock_room: Mock,
) -> None:
    """Test activate scene is called."""
    # Arrange
    mock_fibaro_client.read_rooms.return_value = [mock_room]
    mock_fibaro_client.read_devices.return_value = [mock_switch]

    with patch("homeassistant.components.fibaro.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, mock_config_entry)
        # Act
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.room_1_test_switch_9"},
            blocking=True,
        )
        # Assert
        assert mock_switch.execute_action.call_count == 1

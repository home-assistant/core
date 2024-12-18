"""Tests for the Duwi switch entity in Home Assistant."""

from collections.abc import Generator
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from duwi_smarthome_sdk.device_scene_models import CustomerDevice
from duwi_smarthome_sdk.manager import Manager
import pytest

from homeassistant.components.duwi.switch import DuwiSwitchEntity, async_setup_entry
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def mock_send_commands() -> Generator[AsyncMock, None, None]:
    """Mock the send_commands method of the device manager."""

    async def mock_send_commands(is_group: bool, body: CustomerDevice | None):
        # Simulate sending commands and returning a response
        return {"code": "10000"}

    with patch(
        "duwi_smarthome_sdk.manager.CustomerClient.control", new_callable=AsyncMock
    ) as mock_method:
        mock_method.side_effect = mock_send_commands
        yield mock_method


@pytest.fixture
def mock_switch(hass: HomeAssistant, mock_send_commands):
    """Create and provide a mock Duwi switch entity."""
    # Create mock instances for the parameters
    mock_device = MagicMock(spec=CustomerDevice)
    mock_device.device_no = "12345"
    mock_device.device_name = "Test Device"
    mock_device.is_group = False
    mock_device.room_name = ""
    mock_device.floor_name = "Floor 1"
    mock_device.device_type = "1-002"
    mock_device.value = {
        "switch": "on",
        "online": True,
    }
    mock_manager = MagicMock(spec=Manager)
    mock_description = MagicMock(spec=SwitchEntityDescription)

    # Set expected attributes for mock objects (if needed)
    mock_description.key = "switch"
    return DuwiSwitchEntity(
        device=mock_device,
        device_manager=mock_manager,
        description=mock_description,
    )


@pytest.fixture
def mock_entry():
    """Create a mock config entry for testing."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.manager = MagicMock(spec=Manager)
    return mock_entry


async def test_async_setup_entry_device_not_found_log(
    hass: HomeAssistant, mock_entry
) -> None:
    """Test that a warning is logged if a device is not found in device_map."""
    # Mock the async_add_entities callback
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    # Simulate a case where the device is not found in the device_map
    mock_entry.runtime_data.manager.device_map = {
        "1-002": None,  # Simulate device not found scenario
    }

    with patch("homeassistant.components.duwi.switch._LOGGER.warning") as mock_warning:
        # Call the async_setup_entry function
        await async_setup_entry(hass, mock_entry, async_add_entities)

        # Ensure the warning log was called when the device is not found
        mock_warning.assert_called_once_with(
            "Device not found in device_map: %s", "1-002"
        )

    # Ensure no entities were added
    async_add_entities.assert_called_once()
    added_entities = async_add_entities.call_args[0][0]
    assert len(added_entities) == 0


async def test_turn_on(hass: HomeAssistant, mock_switch) -> None:
    """Verify the switch turns on as expected."""
    await mock_switch.async_turn_on()
    await hass.async_block_till_done()
    assert mock_switch.is_on, "Switch should be ON."


async def test_turn_off(hass: HomeAssistant, mock_switch) -> None:
    """Ensure the switch turns off correctly."""
    await mock_switch.async_turn_off()
    await hass.async_block_till_done()
    assert not mock_switch.is_on, "Switch should be OFF."


async def test_async_setup_entry(hass: HomeAssistant, mock_entry) -> None:
    """Test the async_setup_entry function for Duwi switch."""
    # Mock the async_add_entities callback
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    # Mock device data in manager
    mock_device_1 = MagicMock(spec=CustomerDevice)
    mock_device_1.device_no = "1-002"
    mock_device_1.device_type_no = "1-002"
    mock_device_1.device_group_type = None

    mock_device_2 = MagicMock(spec=CustomerDevice)
    mock_device_2.device_no = "1-003"
    mock_device_2.device_type_no = "1-003"
    mock_device_2.device_group_type = None

    mock_entry.runtime_data.manager.device_map = {
        "1-002": mock_device_1,
        "1-003": mock_device_2,
    }

    # Call the async_setup_entry function
    await async_setup_entry(hass, mock_entry, async_add_entities)

    # Ensure devices were added
    async_add_entities.assert_called_once()
    added_entities = async_add_entities.call_args[0][0]
    assert len(added_entities) == 2
    assert isinstance(added_entities[0], DuwiSwitchEntity)
    assert isinstance(added_entities[1], DuwiSwitchEntity)


async def test_async_setup_entry_device_not_found(
    hass: HomeAssistant, mock_entry
) -> None:
    """Test async_setup_entry when device is not found in device_map."""
    # Mock the async_add_entities callback
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    # Simulate an empty device_map (no devices found)
    mock_entry.runtime_data.manager.device_map = {}

    # Call the async_setup_entry function
    await async_setup_entry(hass, mock_entry, async_add_entities)

    # Ensure no devices were added
    async_add_entities.assert_called_once()
    added_entities = async_add_entities.call_args[0][0]
    assert len(added_entities) == 0


async def test_async_setup_entry_group_switch(hass: HomeAssistant, mock_entry) -> None:
    """Test async_setup_entry with grouped switches (GROUP_SWITCHES)."""
    # Mock the async_add_entities callback
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    # Mock a group switch
    mock_group_device = MagicMock(spec=CustomerDevice)
    mock_group_device.device_no = "Breaker-001"
    mock_group_device.device_type_no = None
    mock_group_device.device_group_type = "Breaker"

    mock_entry.runtime_data.manager.device_map = {
        "Breaker-001": mock_group_device,
    }

    # Call the async_setup_entry function
    await async_setup_entry(hass, mock_entry, async_add_entities)

    # Ensure group switch was added
    async_add_entities.assert_called_once()
    added_entities = async_add_entities.call_args[0][0]
    assert len(added_entities) == 1
    assert isinstance(added_entities[0], DuwiSwitchEntity)


async def test_device_info(mock_switch):
    """Test Duwi switch entity device_info."""
    info = mock_switch.device_info
    assert info["identifiers"] == {("duwi", "12345")}
    assert info["manufacturer"] == "duwi"
    assert info["model"] == mock_switch.device.device_type
    assert info["name"] == "default room " + mock_switch.device.device_name
    assert (
        info["suggested_area"]
        == f"{mock_switch.device.floor_name} {mock_switch.device.room_name}".strip()
    )


async def test_available(mock_switch):
    """Test available property."""
    mock_switch.device.value = {"online": True}
    assert mock_switch.available is True

    mock_switch.device.value = {"online": False}
    assert mock_switch.available is False

    mock_switch.device.value = {}
    assert mock_switch.available is False

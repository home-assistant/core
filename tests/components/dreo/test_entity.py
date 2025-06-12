"""Tests for the Dreo entity classes."""

from unittest.mock import AsyncMock, MagicMock

from hscloud.hscloudexception import (
    HsCloudAccessDeniedException,
    HsCloudBusinessException,
    HsCloudException,
    HsCloudFlowControlException,
)
import pytest

from homeassistant.components.dreo.entity import DreoEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


class MockDreoEntity(DreoEntity):
    """Mock class for DreoEntity testing."""

    def __init__(self, device, coordinator) -> None:
        """Initialize the test entity."""
        super().__init__(device, coordinator, "test", None)
        self._attr_unique_id = f"{device.get('deviceSn', '')}_test"
        self._attr_name = f"Test {device.get('deviceName', 'Unknown')}"


async def test_entity_properties(hass: HomeAssistant, mock_coordinator) -> None:
    """Test entity properties."""
    device = {
        "deviceSn": "test-device-id",
        "deviceName": "Test Device",
        "model": "DR-HTF001S",
    }

    entity = MockDreoEntity(device, mock_coordinator)

    assert entity.name == "Test Test Device"
    assert entity.unique_id == "test-device-id_test"

    device_info = entity.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("dreo", "test-device-id")}
    assert device_info["name"] == "Test Device"
    assert device_info["model"] == "DR-HTF001S"
    assert entity.available is True


async def test_entity_available_property(hass: HomeAssistant, mock_coordinator) -> None:
    """Test entity available property."""
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    assert entity.available is True

    mock_coordinator.last_update_success = False
    assert entity.available is False

    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    assert entity.available is True


async def test_entity_async_added_to_hass(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_added_to_hass."""
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    entity.hass = hass

    mock_coordinator.async_add_listener = MagicMock()

    await entity.async_added_to_hass()

    assert mock_coordinator.async_add_listener.called


async def test_entity_async_update(hass: HomeAssistant, mock_coordinator) -> None:
    """Test async_update."""
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    mock_coordinator.async_request_refresh = AsyncMock()

    await entity.async_update()

    assert mock_coordinator.async_request_refresh.called


async def test_entity_device_info_missing_data(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test device_info with missing data."""
    device = {"deviceSn": "test-device-id"}
    entity = MockDreoEntity(device, mock_coordinator)

    device_info = entity.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("dreo", "test-device-id")}
    assert "name" in device_info
    assert "model" in device_info


async def test_entity_device_not_found(hass: HomeAssistant, mock_coordinator) -> None:
    """Test entity behavior when device not found."""
    device = {"deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    device_info = entity.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    identifiers = device_info["identifiers"]
    assert len(identifiers) == 1
    domain, device_id = next(iter(identifiers))
    assert domain == "dreo"
    assert device_id


async def test_async_send_command_and_update_success(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test successful command execution."""
    mock_client = MagicMock()
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}

    mock_coordinator.client = mock_client

    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_client.update_status = MagicMock()
    mock_coordinator.async_refresh = AsyncMock()

    await entity.async_send_command_and_update("test_error_key", test_param=True)

    mock_client.update_status.assert_called_once_with("test-device-id", test_param=True)
    mock_coordinator.async_refresh.assert_called_once()


async def test_async_send_command_and_update_cloud_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command execution with cloud exception."""
    mock_client = MagicMock()
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}

    mock_coordinator.client = mock_client

    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_client.update_status = MagicMock(side_effect=HsCloudException("Cloud error"))
    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)


async def test_async_send_command_and_update_business_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command execution with business exception."""
    mock_client = MagicMock()
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}

    mock_coordinator.client = mock_client

    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_client.update_status = MagicMock(
        side_effect=HsCloudBusinessException("Business error")
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)


async def test_entity_without_unique_id_suffix(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity creation without unique_id_suffix."""
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}

    entity = DreoEntity(device, mock_coordinator, None, "Custom Name")

    assert entity.unique_id == "test-device-id"
    assert entity.name == "Custom Name"


async def test_async_send_command_access_denied_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command execution with access denied exception."""
    mock_client = MagicMock()
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}

    mock_coordinator.client = mock_client

    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_client.update_status = MagicMock(
        side_effect=HsCloudAccessDeniedException("Access denied")
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)


async def test_async_send_command_flow_control_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command execution with flow control exception."""
    mock_client = MagicMock()
    device = {"deviceSn": "test-device-id", "deviceName": "Test Device"}

    mock_coordinator.client = mock_client

    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_client.update_status = MagicMock(
        side_effect=HsCloudFlowControlException("Flow control")
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)

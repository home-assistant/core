"""Test dreo entity."""

from unittest.mock import AsyncMock, MagicMock

from hscloud.hscloudexception import (
    HsCloudAccessDeniedException,
    HsCloudBusinessException,
    HsCloudException,
    HsCloudFlowControlException,
)
import pytest

from homeassistant.components.dreo.coordinator import DreoDataUpdateCoordinator
from homeassistant.components.dreo.entity import DreoEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


class MockDreoEntity(DreoEntity):
    """Mock DreoEntity for testing."""

    def __init__(self, device, coordinator) -> None:
        """Initialize mock entity."""
        super().__init__(device, coordinator, "test", None)


@pytest.fixture
def mock_coordinator(hass: HomeAssistant):
    """Return a mock coordinator."""
    coordinator = MagicMock(spec=DreoDataUpdateCoordinator)
    coordinator.last_update_success = True
    coordinator.data = MagicMock()
    coordinator.data.available = True
    coordinator.hass = hass
    coordinator.client = MagicMock()
    return coordinator


async def test_entity_device_info_complete(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity device info with complete device data."""
    device = {
        "deviceSn": "test-device-123",
        "deviceName": "Test Device",
        "model": "DR-HTF001S",
        "moduleFirmwareVersion": "1.0.0",
        "mcuFirmwareVersion": "2.0.0",
    }

    entity = MockDreoEntity(device, mock_coordinator)

    device_info = entity.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("dreo", "test-device-123")}
    assert device_info["name"] == "Test Device"
    assert device_info["model"] == "DR-HTF001S"
    assert device_info["manufacturer"] == "Dreo"
    assert device_info["sw_version"] == "1.0.0"
    assert device_info["hw_version"] == "2.0.0"


async def test_entity_device_info_minimal(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity device info with minimal device data."""
    device = {"deviceSn": "test-device-456"}
    entity = MockDreoEntity(device, mock_coordinator)

    device_info = entity.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("dreo", "test-device-456")}
    assert device_info["manufacturer"] == "Dreo"

    assert "name" in device_info
    assert "model" in device_info


async def test_entity_unique_id_with_suffix(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity unique ID generation with suffix."""
    device = {"deviceSn": "test-device-789", "deviceName": "Test Device"}
    entity = DreoEntity(device, mock_coordinator, "fan", None)

    assert entity.unique_id == "test-device-789_fan"


async def test_entity_unique_id_without_suffix(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity unique ID generation without suffix."""
    device = {"deviceSn": "test-device-abc", "deviceName": "Test Device"}
    entity = DreoEntity(device, mock_coordinator, None, "Custom Name")

    assert entity.unique_id == "test-device-abc"
    assert entity.name == "Custom Name"


async def test_entity_availability_with_coordinator_success(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity availability when coordinator is successful."""
    device = {"deviceSn": "test-device", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    mock_coordinator.last_update_success = True
    mock_coordinator.data.available = True

    assert entity.available is True


async def test_entity_availability_with_coordinator_failure(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity availability when coordinator fails."""
    device = {"deviceSn": "test-device", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    mock_coordinator.last_update_success = False

    assert entity.available is False


async def test_entity_availability_with_no_data(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity availability when coordinator has no data."""
    device = {"deviceSn": "test-device", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    mock_coordinator.last_update_success = True
    mock_coordinator.data = None

    assert entity.available is True  # No data doesn't mean unavailable


async def test_entity_send_command_success(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test successful command sending."""
    device = {"deviceSn": "test-device-cmd", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_coordinator.client.update_status = MagicMock()
    mock_coordinator.async_refresh = AsyncMock()

    await entity.async_send_command_and_update("test_error_key", test_param=True)

    mock_coordinator.client.update_status.assert_called_once_with(
        "test-device-cmd", test_param=True
    )
    mock_coordinator.async_refresh.assert_called_once()


async def test_entity_send_command_hscloud_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command sending with HsCloud exception."""
    device = {"deviceSn": "test-device-error", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_coordinator.client.update_status = MagicMock(
        side_effect=HsCloudException("API Error")
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)


async def test_entity_send_command_business_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command sending with business exception."""
    device = {"deviceSn": "test-device-biz", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_coordinator.client.update_status = MagicMock(
        side_effect=HsCloudBusinessException("Business Error")
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)


async def test_entity_send_command_access_denied_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command sending with access denied exception."""
    device = {"deviceSn": "test-device-access", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_coordinator.client.update_status = MagicMock(
        side_effect=HsCloudAccessDeniedException("Access Denied")
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)


async def test_entity_send_command_flow_control_exception(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test command sending with flow control exception."""
    device = {"deviceSn": "test-device-flow", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_coordinator.client.update_status = MagicMock(
        side_effect=HsCloudFlowControlException("Rate Limited")
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command_and_update("test_error_key", test_param=True)


async def test_entity_coordinator_listener_registration(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity registers with coordinator for updates."""
    device = {"deviceSn": "test-device-listener", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)
    entity.hass = hass

    mock_coordinator.async_add_listener = MagicMock()

    await entity.async_added_to_hass()

    mock_coordinator.async_add_listener.assert_called_once()


async def test_entity_async_update_calls_coordinator(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity async_update calls coordinator refresh."""
    device = {"deviceSn": "test-device-update", "deviceName": "Test Device"}
    entity = MockDreoEntity(device, mock_coordinator)

    mock_coordinator.async_request_refresh = AsyncMock()

    await entity.async_update()

    mock_coordinator.async_request_refresh.assert_called_once()


async def test_entity_missing_device_sn_fallback(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test entity handles missing deviceSn gracefully."""
    device = {"deviceName": "Test Device Without SN"}
    entity = MockDreoEntity(device, mock_coordinator)

    device_info = entity.device_info
    assert device_info is not None
    assert "identifiers" in device_info

    assert entity.unique_id is not None

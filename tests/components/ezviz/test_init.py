"""Tests for EZVIZ entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.ezviz.const import ATTR_TYPE_CLOUD
from homeassistant.components.ezviz.image import EzvizLastMotion
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


def _mock_camera_data(**kwargs: object) -> dict[str, object]:
    """Return a valid mocked EZVIZ camera payload for integration setup."""
    data: dict[str, object] = {
        "name": "Camera 1",
        "device_sub_category": "CAMERA",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "version": "1.0.0",
        "status": 1,
        "encrypted": False,
        "supportExt": {},
        "switches": {},
        "local_ip": "192.168.1.100",
        "local_rtsp_port": 554,
        "alarm_notify": False,
        "upgrade_available": False,
        "upgrade_in_progress": False,
        "upgrade_percent": 0,
        "latest_firmware_info": None,
    }
    data.update(kwargs)
    return data


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain="ezviz",
        unique_id="test-username",
        title="test-username",
        data={
            "session_id": "test-username",
            "rf_session_id": "test-password",
            "url": "apiieu.ezvizlife.com",
            "type": ATTR_TYPE_CLOUD,
        },
    )


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_image_entity_has_last_alarm_pic_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test that image entity includes last_alarm_pic as an attribute."""
    # Mock coordinator data with last_alarm_pic
    mock_coordinator_data = {
        "C123456789": _mock_camera_data(
            last_alarm_time="2023-01-01T12:00:00Z",
            last_alarm_pic="https://example.com/image.jpg",
        )
    }

    # Mock the load_cameras method to return our test data
    mock_ezviz_client.load_cameras.return_value = mock_coordinator_data

    await setup_integration(hass, mock_config_entry)

    # Check that image entity was created with the attribute
    state = hass.states.get("image.camera_1_last_motion_image")
    assert state is not None
    assert state.attributes.get("last_alarm_pic") == "https://example.com/image.jpg"

    # Check that last_alarm_pic is in unrecorded attributes
    assert "last_alarm_pic" in EzvizLastMotion._unrecorded_attributes


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_last_alarm_pic_sensor_not_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test that last_alarm_pic sensor is not created."""
    # Mock coordinator data with all sensor fields
    mock_coordinator_data = {
        "C123456789": _mock_camera_data(
            battery_level=85,
            alarm_sound_mod="soft",
            last_alarm_time="2023-01-01T12:00:00Z",
            last_alarm_pic="https://example.com/image.jpg",
            supported_channels=1,
            local_ip="192.168.1.100",
            wan_ip="203.0.113.1",
            PIR_Status="active",
            last_alarm_type_code="motion",
            last_alarm_type_name="Motion Detected",
        )
    }

    # Mock the load_cameras method to return our test data
    mock_ezviz_client.load_cameras.return_value = mock_coordinator_data

    await setup_integration(hass, mock_config_entry)

    # Check that last_alarm_pic sensor was NOT created
    last_alarm_pic_state = hass.states.get("sensor.camera_1_last_alarm_pic")
    assert last_alarm_pic_state is None

    # But other sensors should be created
    registry = er.async_get(hass)
    battery_entity = registry.async_get("sensor.camera_1_battery")
    assert battery_entity is not None


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_migrated_last_alarm_pic_sensor_is_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrated last_alarm_pic sensor entities are removed on setup."""
    mock_config_entry.add_to_hass(hass)

    migrated_entry = entity_registry.async_get_or_create(
        "sensor",
        "ezviz",
        "C123456789_Camera 1.last_alarm_pic",
        config_entry=mock_config_entry,
    )
    mock_ezviz_client.load_cameras.return_value = {
        "C123456789": _mock_camera_data(
            last_alarm_time="2023-01-01T12:00:00Z",
            last_alarm_pic="https://example.com/image.jpg",
        )
    }

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(migrated_entry.entity_id) is None


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_image_entity_not_created_without_alarm_pic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test that image entity is not created when last_alarm_pic is missing."""
    # Mock coordinator data without last_alarm_pic
    mock_coordinator_data = {
        "C123456789": _mock_camera_data(
            battery_level=85,
        )
    }

    # Mock the load_cameras method to return our test data
    mock_ezviz_client.load_cameras.return_value = mock_coordinator_data

    await setup_integration(hass, mock_config_entry)

    # Check that image entity was NOT created
    state = hass.states.get("image.camera_1_last_motion_image")
    assert state is None


@pytest.mark.usefixtures("mock_ezviz_client")
async def test_image_entity_updates_last_alarm_pic_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test the image entity updates its alarm picture on refresh."""
    mock_ezviz_client.load_cameras.return_value = {
        "C123456789": _mock_camera_data(
            last_alarm_time="2023-01-01T12:00:00Z",
            last_alarm_pic="https://example.com/image-1.jpg",
        )
    }

    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    mock_ezviz_client.load_cameras.return_value = {
        "C123456789": _mock_camera_data(
            last_alarm_time="2023-01-01T12:05:00Z",
            last_alarm_pic="https://example.com/image-2.jpg",
        )
    }

    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("image.camera_1_last_motion_image")
    assert state is not None
    assert state.attributes.get("last_alarm_pic") == "https://example.com/image-2.jpg"

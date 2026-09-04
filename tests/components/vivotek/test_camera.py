"""Tests for the Vivotek camera integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from libpyvivotek.vivotek import VivotekCameraError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    SERVICE_DISABLE_MOTION,
    SERVICE_ENABLE_MOTION,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.vivotek.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_camera_device_info(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the camera is linked to a device with expected metadata."""
    mock_vivotek_camera.get_serial.return_value = "ABCD1234"
    mock_vivotek_camera.get_param.side_effect = lambda key: {
        "system_info_firmwareversion": "1.2.3",
        "system_info_modelname": "FD9165-HT",
    }[key]

    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get("camera.vivotek_camera")
    assert entity_entry is not None
    assert entity_entry.device_id is not None

    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert (DOMAIN, "11:22:33:44:55:66") in device.identifiers
    assert device.manufacturer == "VIVOTEK"
    assert device.model == "FD9165-HT"
    assert device.serial_number == "ABCD1234"
    assert device.sw_version == "1.2.3"


async def test_camera_device_info_with_metadata_errors(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test metadata fields are omitted when camera metadata calls fail."""
    mock_vivotek_camera.get_serial.side_effect = VivotekCameraError
    mock_vivotek_camera.get_param.side_effect = VivotekCameraError

    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get("camera.vivotek_camera")
    assert entity_entry is not None
    assert entity_entry.device_id is not None

    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.model is None
    assert device.serial_number is None
    assert device.sw_version is None


async def test_camera_available_when_update_succeeds(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera is available when update probe succeeds."""
    await setup_integration(hass, mock_config_entry)

    freezer.tick(timedelta(seconds=1))
    await async_update_entity(hass, "camera.vivotek_camera")

    state = hass.states.get("camera.vivotek_camera")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_camera_unavailable_when_update_fails(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera is unavailable when update probe raises error."""
    await setup_integration(hass, mock_config_entry)

    mock_vivotek_camera.get_serial.side_effect = VivotekCameraError
    freezer.tick(timedelta(seconds=1))
    await async_update_entity(hass, "camera.vivotek_camera")

    state = hass.states.get("camera.vivotek_camera")
    assert state is not None

    assert state.state == STATE_UNAVAILABLE


async def test_camera_stream_source(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stream source is returned from camera entity."""
    await setup_integration(hass, mock_config_entry)

    stream_source = await async_get_stream_source(hass, "camera.vivotek_camera")

    assert stream_source == "rtsp://admin:pass1234@1.2.3.4:554//live.sdp"


async def test_camera_motion_detection_methods(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test motion detection commands update entity state."""
    await setup_integration(hass, mock_config_entry)

    mock_vivotek_camera.set_param.side_effect = ["1", "0"]

    await hass.services.async_call(
        "camera",
        SERVICE_ENABLE_MOTION,
        {"entity_id": "camera.vivotek_camera"},
        blocking=True,
    )

    await hass.services.async_call(
        "camera",
        SERVICE_DISABLE_MOTION,
        {"entity_id": "camera.vivotek_camera"},
        blocking=True,
    )

    mock_vivotek_camera.set_param.assert_any_call("event_i0_enable", 1)
    mock_vivotek_camera.set_param.assert_any_call("event_i0_enable", 0)


async def test_camera_image_returns_snapshot(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera image comes directly from camera snapshot call."""
    await setup_integration(hass, mock_config_entry)

    mock_vivotek_camera.snapshot.return_value = b"snapshot-bytes"

    image = await async_get_image(hass, "camera.vivotek_camera")

    assert image.content == b"snapshot-bytes"

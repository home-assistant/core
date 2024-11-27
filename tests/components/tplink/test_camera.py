"""The tests for the tplink camera platform."""

from datetime import timedelta
from unittest.mock import patch

from aiohttp.test_utils import make_mocked_request
from freezegun.api import FrozenDateTimeFactory
from kasa import Module
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    CameraEntityFeature,
    StreamType,
    async_get_image,
    async_get_mjpeg_stream,
    get_camera_from_entity_id,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import _mocked_device, setup_platform_for_device, snapshot_platform

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

SMALLEST_VALID_JPEG = (
    "ffd8ffe000104a46494600010101004800480000ffdb00430003020202020203020202030303030406040404040408060"
    "6050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b08000100"
    "0101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)
SMALLEST_VALID_JPEG_BYTES = bytes.fromhex(SMALLEST_VALID_JPEG)


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_config_entry.add_to_hass(hass)

    device = _mocked_device(modules=[Module.Camera], alias="my_camera")

    # Patch getrandbits so the access_token doesn't change on camera attributes
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_platform_for_device(
            hass, mock_config_entry, Platform.CAMERA, device
        )

    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )


async def test_handle_mjpeg_stream(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handle_async_mjpeg_stream."""
    mock_device = _mocked_device(modules=[Module.Camera], alias="my_camera")
    mock_camera = mock_device.modules[Module.Camera]

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None

    mock_request = make_mocked_request("GET", "/", headers={"token": "x"})
    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.my_camera_live_view"
    )
    assert stream is not None

    mock_camera.stream_rtsp_url.return_value = None

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.my_camera_live_view"
    )
    assert stream is None


async def test_camera_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_get_image."""
    mock_device = _mocked_device(modules=[Module.Camera], alias="my_camera")

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None

    with (
        patch(
            "homeassistant.components.tplink.camera.ffmpeg.async_get_image",
            return_value=SMALLEST_VALID_JPEG_BYTES,
        ),
    ):
        image = await async_get_image(hass, "camera.my_camera_live_view")
    assert image
    assert image.content == SMALLEST_VALID_JPEG_BYTES


async def test_camera_stream_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test async_get_image.

    This test would fail if the integration didn't properly
    put stream in the dependencies.
    """
    mock_device = _mocked_device(modules=[Module.Camera], alias="my_camera")

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "camera/stream", "entity_id": "camera.my_camera_live_view"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "url" in msg["result"]


async def test_camera_stream_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stream attributes."""
    mock_device = _mocked_device(modules=[Module.Camera], alias="my_camera")

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None

    supported_features = state.attributes.get("supported_features")
    assert supported_features is CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF
    camera = get_camera_from_entity_id(hass, "camera.my_camera_live_view")
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.HLS}


async def test_camera_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera turn on and off."""
    mock_device = _mocked_device(modules=[Module.Camera], alias="my_camera")
    mock_camera = mock_device.modules[Module.Camera]

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None

    await hass.services.async_call(
        "camera",
        "turn_on",
        {"entity_id": "camera.my_camera_live_view"},
        blocking=True,
    )
    mock_camera.set_state.assert_called_with(True)

    await hass.services.async_call(
        "camera",
        "turn_off",
        {"entity_id": "camera.my_camera_live_view"},
        blocking=True,
    )
    mock_camera.set_state.assert_called_with(False)

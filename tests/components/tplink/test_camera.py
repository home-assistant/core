"""The tests for the tplink camera platform."""

from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import make_mocked_request
import av
from freezegun.api import FrozenDateTimeFactory
from kasa import Module
import pytest
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
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    IP_ADDRESS3,
    MAC_ADDRESS3,
    SMALLEST_VALID_JPEG_BYTES,
    _mocked_device,
    setup_platform_for_device,
    snapshot_platform,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_states(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_camera_config_entry.add_to_hass(hass)

    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )

    # Patch getrandbits so the access_token doesn't change on camera attributes
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_platform_for_device(
            hass, mock_camera_config_entry, Platform.CAMERA, mock_device
        )

    await snapshot_platform(
        hass,
        entity_registry,
        device_registry,
        snapshot,
        mock_camera_config_entry.entry_id,
    )


async def test_handle_mjpeg_stream(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handle_async_mjpeg_stream."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None

    mock_request = make_mocked_request("GET", "/", headers={"token": "x"})
    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.my_camera_live_view"
    )
    assert stream is not None


async def test_handle_mjpeg_stream_not_supported(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handle_async_mjpeg_stream."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )
    mock_camera = mock_device.modules[Module.Camera]

    mock_camera.stream_rtsp_url.return_value = None

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    mock_request = make_mocked_request("GET", "/", headers={"token": "x"})
    stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.my_camera_live_view"
    )
    assert stream is None


async def test_camera_image(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
) -> None:
    """Test async_get_image."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
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


async def test_camera_image_auth_error(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
    mock_discovery: AsyncMock,
) -> None:
    """Test async_get_image."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    with (
        patch(
            "homeassistant.components.tplink.config_flow.ffmpeg.async_get_image",
            return_value=b"",
        ),
        patch(
            "homeassistant.components.tplink.av.open",
            side_effect=av.HTTPUnauthorizedError(404, "Unauthorized"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await async_get_image(hass, "camera.my_camera_live_view")
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows

    assert result["step_id"] == "camera_auth_confirm"


async def test_camera_stream_source(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test async_get_image.

    This test would fail if the integration didn't properly
    put stream in the dependencies.
    """
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
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
    mock_camera_config_entry: MockConfigEntry,
) -> None:
    """Test stream attributes."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    state = hass.states.get("camera.my_camera_live_view")
    assert state is not None

    supported_features = state.attributes.get("supported_features")
    assert supported_features is CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF
    camera = get_camera_from_entity_id(hass, "camera.my_camera_live_view")
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.HLS}


async def test_camera_turn_on_off(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
) -> None:
    """Test camera turn on and off."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )
    mock_camera = mock_device.modules[Module.Camera]

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
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

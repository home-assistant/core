"""The tests for the tplink camera platform."""

import asyncio
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import make_mocked_request
from freezegun.api import FrozenDateTimeFactory
from kasa import Module, StreamResolution
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import stream
from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    CameraEntityFeature,
    StreamType,
    async_get_image,
    async_get_mjpeg_stream,
    get_camera_from_entity_id,
)
from homeassistant.components.tplink.camera import TPLinkCameraEntity
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import _mocked_device, setup_platform_for_device, snapshot_platform
from .const import DEVICE_ID, IP_ADDRESS3, MAC_ADDRESS3, SMALLEST_VALID_JPEG_BYTES


async def test_states(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test camera states."""
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


async def test_camera_unique_id(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test camera unique id."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
        device_id=DEVICE_ID,
    )

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_camera_config_entry.entry_id
    )
    assert device_entries
    entity_id = "camera.my_camera_live_view"

    assert entity_registry.async_get(entity_id).unique_id == f"{DEVICE_ID}-live_view"


async def test_handle_mjpeg_stream(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
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
) -> None:
    """Test no stream if stream_rtsp_url is None after creation."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )
    mock_camera = mock_device.modules[Module.Camera]

    mock_camera.stream_rtsp_url.side_effect = ("foo", None)

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    mock_request = make_mocked_request("GET", "/", headers={"token": "x"})
    mjpeg_stream = await async_get_mjpeg_stream(
        hass, mock_request, "camera.my_camera_live_view"
    )
    assert mjpeg_stream is None


async def test_camera_image(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
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

    with patch(
        "homeassistant.components.ffmpeg.async_get_image",
        return_value=SMALLEST_VALID_JPEG_BYTES,
    ) as mock_get_image:
        image = await async_get_image(hass, "camera.my_camera_live_view")
        assert image
        assert image.content == SMALLEST_VALID_JPEG_BYTES
        mock_get_image.assert_called_once()

        mock_get_image.reset_mock()
        image = await async_get_image(hass, "camera.my_camera_live_view")
        mock_get_image.assert_not_called()

        freezer.tick(TPLinkCameraEntity.IMAGE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        mock_get_image.reset_mock()
        image = await async_get_image(hass, "camera.my_camera_live_view")
        mock_get_image.assert_called_once()

        freezer.tick(TPLinkCameraEntity.IMAGE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Test image returns None
    with patch(
        "homeassistant.components.ffmpeg.async_get_image",
        return_value=None,
    ) as mock_get_image:
        msg = f"None camera image returned for {IP_ADDRESS3}"
        assert msg not in caplog.text

        mock_get_image.reset_mock()
        image = await async_get_image(hass, "camera.my_camera_live_view")
        mock_get_image.assert_called_once()

        assert msg in caplog.text


def _rtsp_url(
    _credentials: object, stream_resolution: StreamResolution = StreamResolution.SD
) -> str:
    """Return an RTSP url that identifies the requested stream resolution."""
    return f"rtsp://{IP_ADDRESS3}/{stream_resolution}"


@pytest.mark.parametrize(
    ("width", "height", "expected_resolution"),
    [
        (None, None, StreamResolution.SD),
        (320, 180, StreamResolution.SD),
        (640, 360, StreamResolution.SD),
        (1920, 1080, StreamResolution.HD),
        (1920, None, StreamResolution.HD),
        (None, 1080, StreamResolution.HD),
        (320, 1080, StreamResolution.HD),
    ],
)
async def test_camera_image_stream_resolution(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    width: int | None,
    height: int | None,
    expected_resolution: StreamResolution,
) -> None:
    """Test the still image is taken from the stream matching the requested size."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )
    mock_device.modules[Module.Camera].stream_rtsp_url.side_effect = _rtsp_url

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    with patch(
        "homeassistant.components.ffmpeg.async_get_image",
        return_value=SMALLEST_VALID_JPEG_BYTES,
    ) as mock_get_image:
        image = await async_get_image(
            hass, "camera.my_camera_live_view", width=width, height=height
        )

    assert image.content == SMALLEST_VALID_JPEG_BYTES
    mock_get_image.assert_called_once_with(
        hass,
        f"rtsp://{IP_ADDRESS3}/{expected_resolution}",
        width=width,
        height=height,
    )


async def test_camera_image_cache_per_resolution(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the SD and HD still images are cached independently."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )
    mock_device.modules[Module.Camera].stream_rtsp_url.side_effect = _rtsp_url

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    sd_image = SMALLEST_VALID_JPEG_BYTES
    hd_image = SMALLEST_VALID_JPEG_BYTES + b"\x00"

    async def _get_image(_hass, video_url, **__):
        return hd_image if video_url.endswith(StreamResolution.HD) else sd_image

    entity_id = "camera.my_camera_live_view"
    with patch(
        "homeassistant.components.ffmpeg.async_get_image", side_effect=_get_image
    ) as mock_get_image:
        # The SD image is cached, but must not answer an HD request
        image = await async_get_image(hass, entity_id, width=320, height=180)
        assert image.content == sd_image
        assert mock_get_image.call_count == 1

        image = await async_get_image(hass, entity_id, width=1920, height=1080)
        assert image.content == hd_image
        assert mock_get_image.call_count == 2

        # Both are now served from their own cache
        image = await async_get_image(hass, entity_id, width=320, height=180)
        assert image.content == sd_image
        image = await async_get_image(hass, entity_id, width=1920, height=1080)
        assert image.content == hd_image
        assert mock_get_image.call_count == 2

        # Both caches expire after the interval
        freezer.tick(TPLinkCameraEntity.IMAGE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        await async_get_image(hass, entity_id, width=320, height=180)
        await async_get_image(hass, entity_id, width=1920, height=1080)
        assert mock_get_image.call_count == 4


async def test_camera_image_cache_per_requested_size(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
) -> None:
    """Test a still scaled for a small request is not served to a larger one."""
    mock_device = _mocked_device(
        modules=[Module.Camera],
        alias="my_camera",
        ip_address=IP_ADDRESS3,
        mac=MAC_ADDRESS3,
    )
    mock_device.modules[Module.Camera].stream_rtsp_url.side_effect = _rtsp_url

    await setup_platform_for_device(
        hass, mock_camera_config_entry, Platform.CAMERA, mock_device
    )

    small_image = SMALLEST_VALID_JPEG_BYTES
    large_image = SMALLEST_VALID_JPEG_BYTES + b"\x00"

    async def _get_image(_hass, _video_url, *, width, **__):
        return small_image if width == 800 else large_image

    entity_id = "camera.my_camera_live_view"
    with patch(
        "homeassistant.components.ffmpeg.async_get_image", side_effect=_get_image
    ) as mock_get_image:
        image = await async_get_image(hass, entity_id, width=800, height=450)
        assert image.content == small_image
        assert mock_get_image.call_count == 1

        image = await async_get_image(hass, entity_id, width=1920, height=1080)
        assert image.content == large_image
        assert mock_get_image.call_count == 2

        image = await async_get_image(hass, entity_id, width=800, height=450)
        assert image.content == small_image
        assert mock_get_image.call_count == 2


async def test_no_camera_image_when_streaming(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test no camera image when streaming."""
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

    with patch(
        "homeassistant.components.ffmpeg.async_get_image",
        return_value=SMALLEST_VALID_JPEG_BYTES,
    ) as mock_get_image:
        await async_get_image(hass, "camera.my_camera_live_view")
        mock_get_image.assert_called_once()

        freezer.tick(TPLinkCameraEntity.IMAGE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        start_event = asyncio.Event()
        finish_event = asyncio.Event()

        async def _waiter(*_, **__):
            start_event.set()
            await finish_event.wait()

        async def _get_stream():
            mock_request = make_mocked_request("GET", "/", headers={"token": "x"})
            await async_get_mjpeg_stream(
                hass, mock_request, "camera.my_camera_live_view"
            )

        mock_get_image.reset_mock()
        with patch(
            "homeassistant.components.tplink.camera.async_aiohttp_proxy_stream",
            new=_waiter,
        ):
            task = asyncio.create_task(_get_stream())
            await start_event.wait()
            await async_get_image(hass, "camera.my_camera_live_view")
            finish_event.set()
            await task

        mock_get_image.assert_not_called()


async def test_no_concurrent_camera_image(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
) -> None:
    """Test async_get_image doesn't make concurrent requests."""
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

    finish_event = asyncio.Event()
    call_count = 0

    async def _waiter(*_, **__):
        nonlocal call_count
        call_count += 1
        await finish_event.wait()
        return SMALLEST_VALID_JPEG_BYTES

    with patch(
        "homeassistant.components.ffmpeg.async_get_image",
        new=_waiter,
    ):
        tasks = asyncio.gather(
            async_get_image(hass, "camera.my_camera_live_view"),
            async_get_image(hass, "camera.my_camera_live_view"),
        )
        # Sleep to give both tasks chance to get to th asyncio.Lock()
        await asyncio.sleep(0)
        finish_event.set()
        results = await tasks
        assert len(results) == 2
        assert all(img and img.content == SMALLEST_VALID_JPEG_BYTES for img in results)
        assert call_count == 1


async def test_camera_image_auth_error(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
    mock_discovery: AsyncMock,
) -> None:
    """Test async_get_image auth error."""
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
            "homeassistant.components.ffmpeg.async_get_image",
            return_value=b"",
        ),
        patch(
            "homeassistant.components.stream.async_check_stream_client_error",
            side_effect=stream.StreamOpenClientError(
                "Request was unauthorized",
                error_code=stream.StreamClientError.Unauthorized,
            ),
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
    """Test camera stream source.

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
        CAMERA_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": "camera.my_camera_live_view"},
        blocking=True,
    )
    mock_camera.set_state.assert_called_with(True)

    await hass.services.async_call(
        CAMERA_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": "camera.my_camera_live_view"},
        blocking=True,
    )
    mock_camera.set_state.assert_called_with(False)

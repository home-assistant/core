"""The tests for the tplink camera platform."""

import asyncio
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import make_mocked_request
from freezegun.api import FrozenDateTimeFactory
from kasa import Module
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import stream
from homeassistant.components.camera import (
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

from . import (
    DEVICE_ID,
    IP_ADDRESS3,
    MAC_ADDRESS3,
    SMALLEST_VALID_JPEG_BYTES,
    _mocked_device,
    setup_platform_for_device,
    snapshot_platform,
)

from tests.common import MockConfigEntry, async_fire_time_changed
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


async def test_camera_unique_id(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
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
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == f"{DEVICE_ID}-live_view"


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


async def test_no_camera_image_when_streaming(
    hass: HomeAssistant,
    mock_camera_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
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
    freezer: FrozenDateTimeFactory,
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

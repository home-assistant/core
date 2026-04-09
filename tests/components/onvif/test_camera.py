"""Test camera of ONVIF integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from onvif.exceptions import ONVIFError
import pytest

from homeassistant.components.onvif.camera import ONVIFCameraEntity
from homeassistant.components.onvif.models import (
    Capabilities,
    Profile,
    Resolution,
    Video,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MAC, setup_onvif_integration


async def test_camera_created(hass: HomeAssistant) -> None:
    """Test camera entity is created."""

    await setup_onvif_integration(
        hass,
        capabilities=Capabilities(imaging=True, ptz=True, snapshot=True),
    )

    entity_registry = er.async_get(hass)
    camera_entries = [
        e for e in entity_registry.entities.values() if e.domain == "camera"
    ]
    assert len(camera_entries) == 1
    assert camera_entries[0].unique_id == f"{MAC}#dummy"


async def test_camera_snapshot_direct(hass: HomeAssistant) -> None:
    """Test camera snapshot directly."""

    mock_device = MagicMock()
    mock_device.capabilities.snapshot = True
    mock_device.config_entry.options = {}
    mock_device.config_entry.data = {}
    mock_device.max_resolution = 640

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    mock_device.device.get_snapshot = AsyncMock(return_value=b"image_data")

    image = await camera.async_camera_image()
    assert image == b"image_data"


async def test_camera_snapshot_error(hass: HomeAssistant) -> None:
    """Test camera snapshot when ONVIFError occurs."""

    mock_device = MagicMock()
    mock_device.capabilities.snapshot = True
    mock_device.config_entry.options = {}
    mock_device.config_entry.data = {}
    mock_device.max_resolution = 640

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    mock_device.device.get_snapshot = AsyncMock(side_effect=ONVIFError("error"))

    with (
        patch(
            "homeassistant.components.onvif.camera.ffmpeg.async_get_image",
            new_callable=AsyncMock,
            return_value=b"ffmpeg_image",
        ) as mock_ffmpeg,
        patch.object(
            camera, "_async_get_stream_uri", AsyncMock(return_value="rtsp://test")
        ),
    ):
        image = await camera.async_camera_image()
        assert image == b"ffmpeg_image"
        mock_ffmpeg.assert_called_once()


async def test_camera_snapshot_none(hass: HomeAssistant) -> None:
    """Test camera snapshot when snapshot returns None."""

    mock_device = MagicMock()
    mock_device.capabilities.snapshot = True
    mock_device.config_entry.options = {}
    mock_device.config_entry.data = {}
    mock_device.max_resolution = 640

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    mock_device.device.get_snapshot = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.onvif.camera.ffmpeg.async_get_image",
            new_callable=AsyncMock,
            return_value=b"ffmpeg_image",
        ) as mock_ffmpeg,
        patch.object(
            camera, "_async_get_stream_uri", AsyncMock(return_value="rtsp://test")
        ),
    ):
        image = await camera.async_camera_image()
        assert image == b"ffmpeg_image"
        mock_ffmpeg.assert_called_once()


async def test_get_stream_uri_cached(hass: HomeAssistant) -> None:
    """Test that stream URI is cached after first call."""

    mock_device = MagicMock()
    mock_device.capabilities.snapshot = False
    mock_device.config_entry.options = {}
    mock_device.config_entry.data = {}
    mock_device.max_resolution = 640
    mock_device.username = "admin"
    mock_device.password = "12345"
    mock_device.async_get_stream_uri = AsyncMock(return_value="rtsp://1.2.3.4/stream")

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    uri1 = await camera._async_get_stream_uri()
    uri2 = await camera._async_get_stream_uri()
    assert uri1 == uri2
    mock_device.async_get_stream_uri.assert_awaited_once()


async def test_get_stream_uri_error(hass: HomeAssistant) -> None:
    """Test getting stream URI when error occurs."""

    mock_device = MagicMock()
    mock_device.capabilities.snapshot = False
    mock_device.config_entry.options = {}
    mock_device.config_entry.data = {}
    mock_device.max_resolution = 640
    mock_device.async_get_stream_uri = AsyncMock(side_effect=TimeoutError("timeout"))

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    with pytest.raises(TimeoutError):
        await camera._async_get_stream_uri()

    # Clean up the future
    if camera._stream_uri_future and not camera._stream_uri_future.done():
        camera._stream_uri_future.cancel()
    await hass.async_block_till_done()


async def test_use_stream_for_stills(hass: HomeAssistant) -> None:
    """Test use_stream_for_stills property."""

    mock_device = MagicMock()
    mock_device.config_entry.options = {}
    mock_device.config_entry.data = {}
    mock_device.max_resolution = 640

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    # No stream → False
    assert camera.use_stream_for_stills is False


async def test_stream_source(hass: HomeAssistant) -> None:
    """Test stream_source returns stream URI."""

    mock_device = MagicMock()
    mock_device.config_entry.options = {}
    mock_device.config_entry.data = {}
    mock_device.max_resolution = 640
    mock_device.username = "admin"
    mock_device.password = "12345"
    mock_device.async_get_stream_uri = AsyncMock(return_value="rtsp://1.2.3.4/stream")

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    uri = await camera.stream_source()
    assert "1.2.3.4" in uri


async def test_handle_mjpeg_stream(hass: HomeAssistant) -> None:
    """Test MJPEG stream handler."""
    mock_device = MagicMock()
    mock_device.config_entry.options = {}
    mock_device.max_resolution = 640

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    mock_stream = AsyncMock()
    mock_stream.get_reader = AsyncMock(return_value=MagicMock())
    mock_request = MagicMock()

    with (
        patch(
            "homeassistant.components.onvif.camera.CameraMjpeg",
            return_value=mock_stream,
        ),
        patch(
            "homeassistant.components.onvif.camera.get_ffmpeg_manager"
        ) as mock_ffmpeg_mgr,
        patch(
            "homeassistant.components.onvif.camera.async_aiohttp_proxy_stream",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as mock_proxy,
        patch.object(
            camera, "_async_get_stream_uri", AsyncMock(return_value="rtsp://test")
        ),
    ):
        mock_ffmpeg_mgr.return_value.binary = "/usr/bin/ffmpeg"
        mock_ffmpeg_mgr.return_value.ffmpeg_stream_content_type = (
            "multipart/x-mixed-replace"
        )
        await camera.handle_async_mjpeg_stream(mock_request)
        mock_proxy.assert_called_once()
        mock_stream.close.assert_called_once()


async def test_get_stream_uri_concurrent(hass: HomeAssistant) -> None:
    """Test that concurrent calls to _async_get_stream_uri wait for the first."""

    mock_device = MagicMock()
    mock_device.username = "admin"
    mock_device.password = "12345"
    mock_device.async_get_stream_uri = AsyncMock(return_value="rtsp://1.2.3.4/stream")

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    # Simulate future already in progress
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    future.set_result("rtsp://admin:12345@1.2.3.4/stream")
    camera._stream_uri_future = future

    uri = await camera._async_get_stream_uri()
    assert "1.2.3.4" in uri
    mock_device.async_get_stream_uri.assert_not_awaited()


async def test_async_perform_ptz(hass: HomeAssistant) -> None:
    """Test PTZ action is called on the device."""
    mock_device = MagicMock()
    mock_device.async_perform_ptz = AsyncMock()
    mock_device.config_entry.options = {}
    mock_device.max_resolution = 640

    profile = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("H264", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )

    camera = ONVIFCameraEntity(mock_device, profile)
    camera.hass = hass

    await camera.async_perform_ptz(
        distance=0.5,
        move_mode="continuous",
        continuous_duration=1.0,
        preset="1",
        speed=0.5,
    )
    mock_device.async_perform_ptz.assert_called_once()

"""Test camera media source."""

from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.camera.const import StreamType
from homeassistant.components.stream import FORMAT_CONTENT_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_media_source(hass):
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


async def test_device_with_device(
    hass: HomeAssistant, mock_camera_with_device, mock_camera
) -> None:
    """Test browsing when camera has a device and a name."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item.not_shown == 2
    assert len(item.children) == 1
    assert item.children[0].title == "Test Camera Device Demo camera without stream"


async def test_device_with_no_name(
    hass: HomeAssistant, mock_camera_with_no_name, mock_camera
) -> None:
    """Test browsing when camera has device and name == None."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item.not_shown == 2
    assert len(item.children) == 1
    assert item.children[0].title == "Test Camera Device Demo camera without stream"


async def test_browsing_hls(hass: HomeAssistant, mock_camera_hls) -> None:
    """Test browsing HLS camera media source."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item is not None
    assert item.title == "Camera"
    assert len(item.children) == 0
    assert item.not_shown == 3

    # Adding stream enables HLS camera
    hass.config.components.add("stream")

    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item.not_shown == 0
    assert len(item.children) == 3
    assert item.children[0].media_content_type == FORMAT_CONTENT_TYPE["hls"]


async def test_browsing_mjpeg(hass: HomeAssistant, mock_camera) -> None:
    """Test browsing MJPEG camera media source."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item is not None
    assert item.title == "Camera"
    assert len(item.children) == 1
    assert item.not_shown == 2
    assert item.children[0].media_content_type == "image/jpg"
    assert item.children[0].title == "Demo camera without stream"


async def test_browsing_web_rtc(hass: HomeAssistant, mock_camera_web_rtc) -> None:
    """Test browsing WebRTC camera media source."""
    # 3 cameras:
    # one only supports WebRTC (no stream source)
    # one raises when getting the source
    # One has a stream source, and should be the only browsable one
    with patch(
        "homeassistant.components.camera.Camera.stream_source",
        side_effect=["test", None, Exception],
    ):
        item = await media_source.async_browse_media(hass, "media-source://camera")
        assert item is not None
        assert item.title == "Camera"
        assert len(item.children) == 0
        assert item.not_shown == 3

        # Adding stream enables HLS camera
        hass.config.components.add("stream")

        item = await media_source.async_browse_media(hass, "media-source://camera")
        assert item.not_shown == 2
        assert len(item.children) == 1
        assert item.children[0].media_content_type == FORMAT_CONTENT_TYPE["hls"]


async def test_resolving(hass: HomeAssistant, mock_camera_hls) -> None:
    """Test resolving."""
    # Adding stream enables HLS camera
    hass.config.components.add("stream")

    with patch(
        "homeassistant.components.camera.media_source._async_stream_endpoint_url",
        return_value="http://example.com/stream",
    ):
        item = await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert item is not None
    assert item.url == "http://example.com/stream"
    assert item.mime_type == FORMAT_CONTENT_TYPE["hls"]


async def test_resolving_errors(hass: HomeAssistant, mock_camera_hls) -> None:
    """Test resolving."""

    with pytest.raises(media_source.Unresolvable) as exc_info:
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert str(exc_info.value) == "Stream integration not loaded"

    hass.config.components.add("stream")

    with pytest.raises(media_source.Unresolvable) as exc_info:
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.non_existing", None
        )
    assert str(exc_info.value) == "Could not resolve media item: camera.non_existing"

    with (
        pytest.raises(media_source.Unresolvable) as exc_info,
        patch(
            "homeassistant.components.camera.Camera.frontend_stream_type",
            new_callable=PropertyMock(return_value=StreamType.WEB_RTC),
        ),
    ):
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert str(exc_info.value) == "Camera does not support MJPEG or HLS streaming."

    with pytest.raises(media_source.Unresolvable) as exc_info:
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert (
        str(exc_info.value) == "camera.demo_camera does not support play stream service"
    )

"""Test camera media source."""
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.camera.const import STREAM_TYPE_WEB_RTC
from homeassistant.components.stream.const import FORMAT_CONTENT_TYPE
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_media_source(hass):
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


@pytest.fixture(autouse=True)
async def mock_stream(hass):
    """Mock stream."""
    hass.config.components.add("stream")


async def test_browsing(hass, mock_camera_hls):
    """Test browsing camera media source."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item is not None
    assert item.title == "Camera"
    assert len(item.children) == 2


async def test_browsing_filter_non_hls(hass, mock_camera_web_rtc):
    """Test browsing camera media source hides non-HLS cameras."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item is not None
    assert item.title == "Camera"
    assert len(item.children) == 0


async def test_resolving(hass, mock_camera_hls):
    """Test resolving."""
    with patch(
        "homeassistant.components.camera.media_source._async_stream_endpoint_url",
        return_value="http://example.com/stream",
    ):
        item = await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera"
        )
    assert item is not None
    assert item.url == "http://example.com/stream"
    assert item.mime_type == FORMAT_CONTENT_TYPE["hls"]


async def test_resolving_errors(hass, mock_camera_hls):
    """Test resolving."""
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.non_existing"
        )

    with pytest.raises(media_source.Unresolvable), patch(
        "homeassistant.components.camera.Camera.frontend_stream_type",
        new_callable=PropertyMock(return_value=STREAM_TYPE_WEB_RTC),
    ):
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera"
        )

    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera"
        )

"""Test go2rtc HLS integration with camera component."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.camera import _async_stream_endpoint_url
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.components.camera.common import mock_turbo_jpeg
from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_turbo() -> None:
    """Mock TurboJPEG."""
    mock_turbo_jpeg()


async def test_stream_endpoint_prefers_go2rtc_hls(hass: HomeAssistant) -> None:
    """Test that camera streaming prefers go2rtc HLS when available."""
    # Mock camera
    camera = Mock()
    camera.entity_id = "camera.test"
    camera.stream_source = AsyncMock(return_value="rtsp://example.com/stream")
    camera.async_create_stream = AsyncMock(return_value=None)
    
    # Mock go2rtc HLS provider
    hls_provider = Mock()
    hls_provider.async_is_supported = Mock(return_value=True)
    hls_provider.async_get_stream_url = AsyncMock(return_value="/api/go2rtc_hls/camera.test/playlist.m3u8")
    
    # Set up hass.data with go2rtc HLS provider
    hass.data["go2rtc"] = {"hls_provider": hls_provider}
    
    # Test that go2rtc HLS is used
    url = await _async_stream_endpoint_url(hass, camera, "hls")
    assert url == "/api/go2rtc_hls/camera.test/playlist.m3u8"
    
    # Verify go2rtc methods were called
    hls_provider.async_is_supported.assert_called_once_with("rtsp://example.com/stream")
    hls_provider.async_get_stream_url.assert_called_once_with(camera)
    
    # Verify stream integration was not used
    camera.async_create_stream.assert_not_called()


async def test_stream_endpoint_fallback_to_stream_integration(hass: HomeAssistant) -> None:
    """Test that camera streaming falls back to stream integration when go2rtc is not available."""
    # Mock camera
    camera = Mock()
    camera.entity_id = "camera.test"
    camera.stream_source = AsyncMock(return_value="rtsp://example.com/stream")
    
    # Mock stream integration
    stream = Mock()
    stream.add_provider = Mock()
    stream.start = AsyncMock()
    stream.endpoint_url = Mock(return_value="/api/hls/token/master_playlist.m3u8")
    camera.async_create_stream = AsyncMock(return_value=stream)
    
    # No go2rtc provider available
    hass.data.clear()
    
    # Test that stream integration is used
    url = await _async_stream_endpoint_url(hass, camera, "hls")
    assert url == "/api/hls/token/master_playlist.m3u8"
    
    # Verify stream integration methods were called
    camera.async_create_stream.assert_called_once()
    stream.add_provider.assert_called_once_with("hls")
    stream.start.assert_called_once()
    stream.endpoint_url.assert_called_once_with("hls")


async def test_stream_endpoint_fallback_when_go2rtc_unsupported(hass: HomeAssistant) -> None:
    """Test fallback to stream integration when go2rtc doesn't support the camera."""
    # Mock camera with unsupported stream source
    camera = Mock()
    camera.entity_id = "camera.test"
    camera.stream_source = AsyncMock(return_value="unsupported://stream")
    
    # Mock stream integration
    stream = Mock()
    stream.add_provider = Mock()
    stream.start = AsyncMock()
    stream.endpoint_url = Mock(return_value="/api/hls/token/master_playlist.m3u8")
    camera.async_create_stream = AsyncMock(return_value=stream)
    
    # Mock go2rtc HLS provider that doesn't support this stream
    hls_provider = Mock()
    hls_provider.async_is_supported = Mock(return_value=False)
    hass.data["go2rtc"] = {"hls_provider": hls_provider}
    
    # Test that stream integration is used
    url = await _async_stream_endpoint_url(hass, camera, "hls")
    assert url == "/api/hls/token/master_playlist.m3u8"
    
    # Verify go2rtc was checked but rejected
    hls_provider.async_is_supported.assert_called_once_with("unsupported://stream")
    
    # Verify stream integration was used as fallback
    camera.async_create_stream.assert_called_once()


async def test_stream_endpoint_fallback_when_go2rtc_fails(hass: HomeAssistant) -> None:
    """Test fallback to stream integration when go2rtc fails."""
    # Mock camera
    camera = Mock()
    camera.entity_id = "camera.test"
    camera.stream_source = AsyncMock(return_value="rtsp://example.com/stream")
    
    # Mock stream integration
    stream = Mock()
    stream.add_provider = Mock()
    stream.start = AsyncMock()
    stream.endpoint_url = Mock(return_value="/api/hls/token/master_playlist.m3u8")
    camera.async_create_stream = AsyncMock(return_value=stream)
    
    # Mock go2rtc HLS provider that fails
    hls_provider = Mock()
    hls_provider.async_is_supported = Mock(return_value=True)
    hls_provider.async_get_stream_url = AsyncMock(side_effect=Exception("go2rtc failed"))
    hass.data["go2rtc"] = {"hls_provider": hls_provider}
    
    # Test that stream integration is used as fallback
    url = await _async_stream_endpoint_url(hass, camera, "hls")
    assert url == "/api/hls/token/master_playlist.m3u8"
    
    # Verify go2rtc was attempted but failed
    hls_provider.async_get_stream_url.assert_called_once_with(camera)
    
    # Verify stream integration was used as fallback
    camera.async_create_stream.assert_called_once()


async def test_stream_endpoint_non_hls_format_uses_stream_integration(hass: HomeAssistant) -> None:
    """Test that non-HLS formats always use stream integration."""
    # Mock camera
    camera = Mock()
    camera.entity_id = "camera.test"
    camera.stream_source = AsyncMock(return_value="rtsp://example.com/stream")
    
    # Mock stream integration
    stream = Mock()
    stream.add_provider = Mock()
    stream.start = AsyncMock()
    stream.endpoint_url = Mock(return_value="/api/recorder/token/recording.mp4")
    camera.async_create_stream = AsyncMock(return_value=stream)
    
    # Mock go2rtc HLS provider (should not be used for non-HLS)
    hls_provider = Mock()
    hass.data["go2rtc"] = {"hls_provider": hls_provider}
    
    # Test with recorder format
    url = await _async_stream_endpoint_url(hass, camera, "recorder")
    assert url == "/api/recorder/token/recording.mp4"
    
    # Verify go2rtc was not used
    assert not hls_provider.method_calls
    
    # Verify stream integration was used
    camera.async_create_stream.assert_called_once()
    stream.add_provider.assert_called_once_with("recorder")
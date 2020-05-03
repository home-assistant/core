"""The tests for stream."""
import pytest

from homeassistant.components.stream.const import (
    ATTR_STREAMS,
    CONF_LOOKBACK,
    CONF_STREAM_SOURCE,
    DOMAIN,
    SERVICE_RECORD,
)
from homeassistant.const import CONF_FILENAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, MagicMock, patch


async def test_record_service_invalid_file(hass):
    """Test record service call with invalid file."""
    await async_setup_component(hass, "stream", {"stream": {}})
    data = {CONF_STREAM_SOURCE: "rtsp://my.video", CONF_FILENAME: "/my/invalid/path"}
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)


async def test_record_service_init_stream(hass):
    """Test record service call with invalid file."""
    await async_setup_component(hass, "stream", {"stream": {}})
    data = {CONF_STREAM_SOURCE: "rtsp://my.video", CONF_FILENAME: "/my/invalid/path"}
    with patch("homeassistant.components.stream.Stream") as stream_mock, patch.object(
        hass.config, "is_allowed_path", return_value=True
    ):
        # Setup stubs
        stream_mock.return_value.outputs = {}

        # Call Service
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)

        # Assert
        assert stream_mock.called


async def test_record_service_existing_record_session(hass):
    """Test record service call with invalid file."""
    await async_setup_component(hass, "stream", {"stream": {}})
    source = "rtsp://my.video"
    data = {CONF_STREAM_SOURCE: source, CONF_FILENAME: "/my/invalid/path"}

    # Setup stubs
    stream_mock = MagicMock()
    stream_mock.return_value.outputs = {"recorder": MagicMock()}
    hass.data[DOMAIN][ATTR_STREAMS][source] = stream_mock

    with patch.object(hass.config, "is_allowed_path", return_value=True), pytest.raises(
        HomeAssistantError
    ):
        # Call Service
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)


async def test_record_service_lookback(hass):
    """Test record service call with invalid file."""
    await async_setup_component(hass, "stream", {"stream": {}})
    data = {
        CONF_STREAM_SOURCE: "rtsp://my.video",
        CONF_FILENAME: "/my/invalid/path",
        CONF_LOOKBACK: 4,
    }

    with patch("homeassistant.components.stream.Stream") as stream_mock, patch.object(
        hass.config, "is_allowed_path", return_value=True
    ):
        # Setup stubs
        hls_mock = MagicMock()
        hls_mock.num_segments = 3
        hls_mock.target_duration = 2
        hls_mock.recv = AsyncMock(return_value=None)
        stream_mock.return_value.outputs = {"hls": hls_mock}

        # Call Service
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)

        assert stream_mock.called
        stream_mock.return_value.add_provider.assert_called_once_with("recorder")
        assert hls_mock.recv.called

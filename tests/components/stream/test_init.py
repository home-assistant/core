"""The tests for stream."""
from typing import Awaitable, Callable

import pytest

from homeassistant.components.stream import StreamSource, request_stream
from homeassistant.components.stream.const import (
    ATTR_STREAMS,
    CONF_LOOKBACK,
    CONF_STREAM_SOURCE,
    DOMAIN,
    SERVICE_RECORD,
)
from homeassistant.const import CONF_FILENAME, EVENT_HOMEASSISTANT_STOP
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
        hls_mock.target_duration = 2
        hls_mock.recv = AsyncMock(return_value=None)
        stream_mock.return_value.outputs = {"hls": hls_mock}

        # Call Service
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)

        assert stream_mock.called
        stream_mock.return_value.add_provider.assert_called_once_with("recorder")
        assert hls_mock.recv.called


def stream_source_cb(source, cache_key=None) -> Callable[[], Awaitable[StreamSource]]:
    """Create a stream source callback for tests."""

    async def callback():
        return StreamSource(source, cache_key=cache_key)

    return callback


async def test_request_stream_started(hass):
    """Tests that two requests for the same stream have the same access token url."""
    await async_setup_component(hass, "stream", {"stream": {}})

    with patch("homeassistant.components.stream.worker.stream_worker"):
        url_1 = await request_stream(hass, stream_source_cb("rtsp:://my_video_1"))
        url_2 = await request_stream(hass, stream_source_cb("rtsp:://my_video_1"))
        assert url_1 == url_2

    # Verify one stream is shut down
    with patch("homeassistant.components.stream.Stream.stop") as mock_stop:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        mock_stop.assert_called_once()


async def test_request_stream_multiple_started(hass):
    """Tests that two different requests have different access token urls."""
    await async_setup_component(hass, "stream", {"stream": {}})

    with patch("homeassistant.components.stream.worker.stream_worker"):
        url_1 = await request_stream(hass, stream_source_cb("rtsp:://my_video_1"))
        url_2 = await request_stream(hass, stream_source_cb("rtsp:://my_video_2"))
        assert url_1 != url_2

    # Verify both streams are shut down
    with patch("homeassistant.components.stream.Stream.stop") as mock_stop:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        assert len(mock_stop.mock_calls) == 2


async def test_request_stream_by_stream_id(hass):
    """Tests for two urls with the same cache key key."""
    await async_setup_component(hass, "stream", {"stream": {}})

    with patch("homeassistant.components.stream.worker.stream_worker"):
        url_1 = await request_stream(
            hass, stream_source_cb("rtsp:://my_video_1", cache_key="some-key")
        )
        url_2 = await request_stream(
            hass, stream_source_cb("rtsp:://my_video_1", cache_key="some-key")
        )
        assert url_1 == url_2

    # Verify one stream is shut down
    with patch("homeassistant.components.stream.Stream.stop") as mock_stop:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        mock_stop.assert_called_once()


async def test_request_stream_updated_by_stream_id(hass):
    """Tests that stream worker is cached and restarted when a url is updated."""
    await async_setup_component(hass, "stream", {"stream": {}})

    with patch("homeassistant.components.stream.worker.stream_worker"):
        url_1 = await request_stream(
            hass, stream_source_cb("rtsp:://my_video_1", cache_key="some-key")
        )
        url_2 = await request_stream(
            hass, stream_source_cb("rtsp:://my_video_2", cache_key="some-key")
        )
        assert url_1 == url_2

    # Verify one stream is shut down
    with patch("homeassistant.components.stream.Stream.stop") as mock_stop:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        mock_stop.assert_called_once()

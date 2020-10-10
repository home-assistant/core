"""The tests for hls streams."""
from datetime import timedelta
from urllib.parse import urlparse

import av
import pytest

from homeassistant.components.stream import request_stream
from homeassistant.const import HTTP_NOT_FOUND
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import async_fire_time_changed
from tests.components.stream.common import generate_h264_video, preload_stream


@pytest.mark.skip("Flaky in CI")
async def test_hls_stream(hass, hass_client):
    """
    Test hls stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    # Setup demo HLS track
    source = generate_h264_video()
    stream = preload_stream(hass, source)
    stream.add_provider("hls")

    # Request stream
    url = request_stream(hass, source)

    http_client = await hass_client()

    # Fetch playlist
    parsed_url = urlparse(url)
    playlist_response = await http_client.get(parsed_url.path)
    assert playlist_response.status == 200

    # Fetch init
    playlist = await playlist_response.text()
    playlist_url = "/".join(parsed_url.path.split("/")[:-1])
    init_url = playlist_url + "/init.mp4"
    init_response = await http_client.get(init_url)
    assert init_response.status == 200

    # Fetch segment
    playlist = await playlist_response.text()
    playlist_url = "/".join(parsed_url.path.split("/")[:-1])
    segment_url = playlist_url + playlist.splitlines()[-1][1:]
    segment_response = await http_client.get(segment_url)
    assert segment_response.status == 200

    # Stop stream, if it hasn't quit already
    stream.stop()

    # Ensure playlist not accessible after stream ends
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == HTTP_NOT_FOUND


@pytest.mark.skip("Flaky in CI")
async def test_stream_timeout(hass, hass_client):
    """Test hls stream timeout."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Setup demo HLS track
    source = generate_h264_video()
    stream = preload_stream(hass, source)
    stream.add_provider("hls")

    # Request stream
    url = request_stream(hass, source)

    http_client = await hass_client()

    # Fetch playlist
    parsed_url = urlparse(url)
    playlist_response = await http_client.get(parsed_url.path)
    assert playlist_response.status == 200

    # Wait a minute
    future = dt_util.utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, future)

    # Fetch again to reset timer
    playlist_response = await http_client.get(parsed_url.path)
    assert playlist_response.status == 200

    # Wait 5 minutes
    future = dt_util.utcnow() + timedelta(minutes=5)
    async_fire_time_changed(hass, future)

    # Ensure playlist not accessible
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == HTTP_NOT_FOUND


@pytest.mark.skip("Flaky in CI")
async def test_stream_ended(hass):
    """Test hls stream packets ended."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Setup demo HLS track
    source = generate_h264_video()
    stream = preload_stream(hass, source)
    track = stream.add_provider("hls")

    # Request stream
    request_stream(hass, source)

    # Run it dead
    while True:
        segment = await track.recv()
        if segment is None:
            break
        segments = segment.sequence

    assert segments > 1
    assert not track.get_segment()

    # Stop stream, if it hasn't quit already
    stream.stop()


async def test_stream_keepalive(hass):
    """Test hls stream retries the stream when keepalive=True."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Setup demo HLS track
    source = "test_stream_keepalive_source"
    stream = preload_stream(hass, source)
    track = stream.add_provider("hls")
    track.num_segments = 2

    cur_time = 0

    def time_side_effect():
        nonlocal cur_time
        if cur_time >= 80:
            stream.keepalive = False  # Thread should exit and be joinable.
        cur_time += 40
        return cur_time

    with patch("av.open") as av_open, patch(
        "homeassistant.components.stream.worker.time"
    ) as mock_time:
        av_open.side_effect = av.error.InvalidDataError(-2, "error")
        mock_time.time.side_effect = time_side_effect
        # Request stream
        request_stream(hass, source, keepalive=True)
        stream._thread.join()
        stream._thread = None
        assert av_open.call_count == 2

    # Stop stream, if it hasn't quit already
    stream.stop()

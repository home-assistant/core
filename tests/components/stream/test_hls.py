"""The tests for hls streams."""
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlparse

import av

from homeassistant.components.stream import create_stream
from homeassistant.const import HTTP_NOT_FOUND
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.stream.common import generate_h264_video


async def test_hls_stream(hass, hass_client, stream_worker_sync):
    """
    Test hls stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    stream_worker_sync.pause()

    # Setup demo HLS track
    source = generate_h264_video()
    stream = create_stream(hass, source)

    # Request stream
    stream.add_provider("hls")
    stream.start()
    url = stream.endpoint_url("hls")

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
    segment_url = playlist_url + "/" + playlist.splitlines()[-1]
    segment_response = await http_client.get(segment_url)
    assert segment_response.status == 200

    stream_worker_sync.resume()

    # Stop stream, if it hasn't quit already
    stream.stop()

    # Ensure playlist not accessible after stream ends
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == HTTP_NOT_FOUND


async def test_stream_timeout(hass, hass_client, stream_worker_sync):
    """Test hls stream timeout."""
    await async_setup_component(hass, "stream", {"stream": {}})

    stream_worker_sync.pause()

    # Setup demo HLS track
    source = generate_h264_video()
    stream = create_stream(hass, source)

    # Request stream
    stream.add_provider("hls")
    stream.start()
    url = stream.endpoint_url("hls")

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

    stream_worker_sync.resume()

    # Wait 5 minutes
    future = dt_util.utcnow() + timedelta(minutes=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # Ensure playlist not accessible
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == HTTP_NOT_FOUND


async def test_stream_ended(hass, stream_worker_sync):
    """Test hls stream packets ended."""
    await async_setup_component(hass, "stream", {"stream": {}})

    stream_worker_sync.pause()

    # Setup demo HLS track
    source = generate_h264_video()
    stream = create_stream(hass, source)
    track = stream.add_provider("hls")

    # Request stream
    stream.add_provider("hls")
    stream.start()
    stream.endpoint_url("hls")

    # Run it dead
    while True:
        segment = await track.recv()
        if segment is None:
            break
        segments = segment.sequence
        # Allow worker to finalize once enough of the stream is been consumed
        if segments > 1:
            stream_worker_sync.resume()

    assert segments > 1
    assert not track.get_segment()

    # Stop stream, if it hasn't quit already
    stream.stop()


async def test_stream_keepalive(hass):
    """Test hls stream retries the stream when keepalive=True."""
    await async_setup_component(hass, "stream", {"stream": {}})

    # Setup demo HLS track
    source = "test_stream_keepalive_source"
    stream = create_stream(hass, source)
    track = stream.add_provider("hls")
    track.num_segments = 2
    stream.start()

    cur_time = 0

    def time_side_effect():
        nonlocal cur_time
        if cur_time >= 80:
            stream.keepalive = False  # Thread should exit and be joinable.
        cur_time += 40
        return cur_time

    with patch("av.open") as av_open, patch(
        "homeassistant.components.stream.time"
    ) as mock_time, patch(
        "homeassistant.components.stream.STREAM_RESTART_INCREMENT", 0
    ):
        av_open.side_effect = av.error.InvalidDataError(-2, "error")
        mock_time.time.side_effect = time_side_effect
        # Request stream
        stream.keepalive = True
        stream.start()
        stream._thread.join()
        stream._thread = None
        assert av_open.call_count == 2

    # Stop stream, if it hasn't quit already
    stream.stop()

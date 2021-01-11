"""The tests for hls streams.

The tests encode stream (as an h264 video), then load the stream and verify
that it is decoded properly. The background worker thread responsible for
decoding will decode the stream as fast as possible, and when completed
clears all output buffers. This can be a problem for the test that wishes
to retrieve and verify decoded segments. If the worker finishes first, there is
nothing for the test to verify. The solution is the WorkerSync class that
allows the tests to pause the worker thread before finalizing the stream
so that it can inspect the output.
"""
from datetime import timedelta
import threading
from unittest.mock import patch
from urllib.parse import urlparse

import av
import pytest

from homeassistant.components.stream import request_stream
from homeassistant.components.stream.core import Segment, StreamOutput
from homeassistant.const import HTTP_NOT_FOUND
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.stream.common import generate_h264_video, preload_stream


class WorkerSync:
    """Test fixture that intercepts stream worker calls to StreamOutput."""

    def __init__(self):
        """Initialize WorkerSync."""
        self._event = None
        self._put_original = StreamOutput.put

    def pause(self):
        """Pause the worker before it finalizes the stream."""
        self._event = threading.Event()

    def resume(self):
        """Allow the worker thread to finalize the stream."""
        self._event.set()

    def blocking_put(self, stream_output: StreamOutput, segment: Segment):
        """Proxy StreamOutput.put, intercepted for test to pause worker."""
        if segment is None and self._event:
            # Worker is ending the stream, which clears all output buffers.
            # Block the worker thread until the test has a chance to verify
            # the segments under test.
            self._event.wait()

        # Forward to actual StreamOutput.put
        self._put_original(stream_output, segment)


@pytest.fixture()
def worker_sync(hass):
    """Patch StreamOutput to allow test to synchronize worker stream end."""
    sync = WorkerSync()
    with patch(
        "homeassistant.components.stream.core.StreamOutput.put",
        side_effect=sync.blocking_put,
        autospec=True,
    ):
        yield sync


async def test_hls_stream(hass, hass_client, worker_sync):
    """
    Test hls stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    worker_sync.pause()

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
    segment_url = playlist_url + "/" + playlist.splitlines()[-1]
    segment_response = await http_client.get(segment_url)
    assert segment_response.status == 200

    worker_sync.resume()

    # Stop stream, if it hasn't quit already
    stream.stop()

    # Ensure playlist not accessible after stream ends
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == HTTP_NOT_FOUND


async def test_stream_timeout(hass, hass_client, worker_sync):
    """Test hls stream timeout."""
    await async_setup_component(hass, "stream", {"stream": {}})

    worker_sync.pause()

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

    worker_sync.resume()

    # Wait 5 minutes
    future = dt_util.utcnow() + timedelta(minutes=5)
    async_fire_time_changed(hass, future)

    # Ensure playlist not accessible
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == HTTP_NOT_FOUND


async def test_stream_ended(hass, worker_sync):
    """Test hls stream packets ended."""
    await async_setup_component(hass, "stream", {"stream": {}})

    worker_sync.pause()

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
        # Allow worker to finalize once enough of the stream is been consumed
        if segments > 1:
            worker_sync.resume()

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
    ) as mock_time, patch(
        "homeassistant.components.stream.worker.STREAM_RESTART_INCREMENT", 0
    ):
        av_open.side_effect = av.error.InvalidDataError(-2, "error")
        mock_time.time.side_effect = time_side_effect
        # Request stream
        request_stream(hass, source, keepalive=True)
        stream._thread.join()
        stream._thread = None
        assert av_open.call_count == 2

    # Stop stream, if it hasn't quit already
    stream.stop()

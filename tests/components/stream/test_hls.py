"""The tests for hls streams."""
from datetime import timedelta
from urllib.parse import urlparse

from homeassistant.setup import async_setup_component
from homeassistant.components.stream import request_stream
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.stream.common import (
    generate_h264_video, preload_stream)


async def test_hls_stream(hass, hass_client):
    """
    Test hls stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """
    await async_setup_component(hass, 'stream', {
        'stream': {}
    })

    # Setup demo HLS track
    source = generate_h264_video()
    stream = preload_stream(hass, source)
    stream.add_provider('hls')

    # Request stream
    url = request_stream(hass, source)

    http_client = await hass_client()

    # Fetch playlist
    parsed_url = urlparse(url)
    playlist_response = await http_client.get(parsed_url.path)
    assert playlist_response.status == 200

    # Fetch segment
    playlist = await playlist_response.text()
    playlist_url = '/'.join(parsed_url.path.split('/')[:-1])
    segment_url = playlist_url + playlist.splitlines()[-1][1:]
    segment_response = await http_client.get(segment_url)
    assert segment_response.status == 200

    # Stop stream, if it hasn't quit already
    stream.stop()

    # Ensure playlist not accessable after stream ends
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == 404


async def test_stream_timeout(hass, hass_client):
    """Test hls stream timeout."""
    await async_setup_component(hass, 'stream', {
        'stream': {}
    })

    # Setup demo HLS track
    source = generate_h264_video()
    stream = preload_stream(hass, source)
    stream.add_provider('hls')

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

    # Ensure playlist not accessable
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == 404


async def test_stream_ended(hass):
    """Test hls stream packets ended."""
    await async_setup_component(hass, 'stream', {
        'stream': {}
    })

    # Setup demo HLS track
    source = generate_h264_video()
    stream = preload_stream(hass, source)
    track = stream.add_provider('hls')
    track.num_segments = 2

    # Request stream
    request_stream(hass, source)

    # Run it dead
    segments = 0
    while await track.recv() is not None:
        segments += 1

    assert segments == 3
    assert not track.get_segment()

    # Stop stream, if it hasn't quit already
    stream.stop()

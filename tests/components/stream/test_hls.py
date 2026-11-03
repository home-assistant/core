"""The tests for hls streams."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from threading import Event
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlparse

import av
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.homekit.hksv_stream import (  # pylint: disable=home-assistant-component-root-import
    SharedCameraStream,
)
from homeassistant.components.stream import Stream, create_stream
from homeassistant.components.stream.const import (
    DOMAIN,
    EXT_X_START_LL_HLS,
    EXT_X_START_NON_LL_HLS,
    HLS_PROVIDER,
    MAX_SEGMENTS,
    NUM_PLAYLIST_SEGMENTS,
)
from homeassistant.components.stream.core import Orientation, Part
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    FAKE_TIME,
    DefaultSegment as Segment,
    assert_mp4_has_transform_matrix,
    dynamic_stream_settings,
)

STREAM_SOURCE = "some-stream-source"
INIT_BYTES = b"\x00\x00\x00\x08moov"
FAKE_PAYLOAD = b"fake-payload"
SEGMENT_DURATION = 10
TEST_TIMEOUT = 5.0  # Lower than 9s home assistant timeout
MAX_ABORT_SEGMENTS = 20  # Abort test to avoid looping forever

HLS_CONFIG = {
    "stream": {
        "ll_hls": False,
    }
}


@pytest.fixture
async def setup_component(hass: HomeAssistant) -> None:
    """Test fixture to setup the stream component."""
    await async_setup_component(hass, DOMAIN, HLS_CONFIG)


class HlsClient:
    """Test fixture for fetching the hls stream."""

    def __init__(self, http_client, parsed_url) -> None:
        """Initialize HlsClient."""
        self.http_client = http_client
        self.parsed_url = parsed_url

    async def get(self, path=None, headers=None):
        """Fetch the hls stream for the specified path."""
        url = self.parsed_url.path
        if path:
            # Strip off the master playlist suffix and replace with path
            url = "/".join(self.parsed_url.path.split("/")[:-1]) + path
        return await self.http_client.get(url, headers=headers)


@pytest.fixture
def hls_stream(hass: HomeAssistant, hass_client: ClientSessionGenerator):
    """Create test fixture for creating an HLS client for a stream."""

    async def create_client_for_stream(stream):
        http_client = await hass_client()
        parsed_url = urlparse(stream.endpoint_url(HLS_PROVIDER))
        return HlsClient(http_client, parsed_url)

    return create_client_for_stream


def make_segment(segment, discontinuity=False):
    """Create a playlist response for a segment."""
    response = ["#EXT-X-DISCONTINUITY"] if discontinuity else []
    response.extend(
        [
            "#EXT-X-PROGRAM-DATE-TIME:"
            + FAKE_TIME.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z",
            f"#EXTINF:{SEGMENT_DURATION:.3f},",
            f"./segment/{segment}.m4s",
        ]
    )
    return "\n".join(response)


def make_playlist(
    sequence,
    discontinuity_sequence=0,
    segments=None,
    hint=None,
    segment_duration=None,
    part_target_duration=None,
):
    """Create a an hls playlist response for tests to assert on."""
    if not segment_duration:
        segment_duration = SEGMENT_DURATION
    response = [
        "#EXTM3U",
        "#EXT-X-VERSION:6",
        "#EXT-X-INDEPENDENT-SEGMENTS",
        '#EXT-X-MAP:URI="init.mp4"',
        f"#EXT-X-TARGETDURATION:{segment_duration}",
        f"#EXT-X-MEDIA-SEQUENCE:{sequence}",
        f"#EXT-X-DISCONTINUITY-SEQUENCE:{discontinuity_sequence}",
    ]
    if hint:
        response.extend(
            [
                f"#EXT-X-PART-INF:PART-TARGET={part_target_duration:.3f}",
                "#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES,PART-HOLD-BACK="
                f"{2 * part_target_duration:.3f}",
                "#EXT-X-START:TIME-OFFSET=-"
                f"{EXT_X_START_LL_HLS * part_target_duration:.3f},PRECISE=YES",
            ]
        )
    else:
        response.append(
            "#EXT-X-START:TIME-OFFSET=-"
            f"{EXT_X_START_NON_LL_HLS * segment_duration:.3f},PRECISE=YES",
        )
    if segments:
        response.extend(segments)
    if hint:
        response.append(hint)
    response.append("")
    return "\n".join(response)


async def test_hls_stream(
    hass: HomeAssistant, setup_component, hls_stream, stream_worker_sync, h264_video
) -> None:
    """Test hls stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """

    stream_worker_sync.pause()

    # Setup demo HLS track
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())

    # Request stream
    stream.add_provider(HLS_PROVIDER)
    await stream.start()

    hls_client = await hls_stream(stream)

    # Fetch master playlist
    master_playlist_response = await hls_client.get()
    assert master_playlist_response.status == HTTPStatus.OK

    # Fetch init
    master_playlist = await master_playlist_response.text()
    init_response = await hls_client.get("/init.mp4")
    assert init_response.status == HTTPStatus.OK

    # Fetch playlist
    playlist_url = "/" + master_playlist.splitlines()[-1]
    playlist_response = await hls_client.get(playlist_url)
    assert playlist_response.status == HTTPStatus.OK

    # Fetch segment
    playlist = await playlist_response.text()
    segment_url = "/" + [line for line in playlist.splitlines() if line][-1]
    segment_response = await hls_client.get(segment_url)
    assert segment_response.status == HTTPStatus.OK

    stream_worker_sync.resume()

    # Stop stream, if it hasn't quit already
    await stream.stop()

    # Ensure playlist not accessible after stream ends
    fail_response = await hls_client.get()
    assert fail_response.status == HTTPStatus.NOT_FOUND

    assert stream.get_diagnostics() == {
        "container_format": "mov,mp4,m4a,3gp,3g2,mj2",
        "keepalive": False,
        "orientation": Orientation.NO_TRANSFORM,
        "start_worker": 1,
        "video_codec": "h264",
        "worker_error": 1,
    }


async def test_stream_timeout(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_component,
    stream_worker_sync,
    h264_video,
) -> None:
    """Test hls stream timeout."""
    stream_worker_sync.pause()

    # Setup demo HLS track
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())

    available_states = []

    def update_callback() -> None:
        nonlocal available_states
        available_states.append(stream.available)

    stream.set_update_callback(update_callback)

    # Request stream
    stream.add_provider(HLS_PROVIDER)
    await stream.start()
    url = stream.endpoint_url(HLS_PROVIDER)

    http_client = await hass_client()

    # Fetch playlist
    parsed_url = urlparse(url)
    playlist_response = await http_client.get(parsed_url.path)
    assert playlist_response.status == HTTPStatus.OK

    # Wait 40 seconds
    future = dt_util.utcnow() + timedelta(seconds=40)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # Fetch again to reset timer
    playlist_response = await http_client.get(parsed_url.path)
    assert playlist_response.status == HTTPStatus.OK

    stream_worker_sync.resume()

    # Wait 2 minutes
    future = dt_util.utcnow() + timedelta(minutes=2)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # Ensure playlist not accessible
    fail_response = await http_client.get(parsed_url.path)
    assert fail_response.status == HTTPStatus.NOT_FOUND

    # Streams only marked as failure when keepalive is true
    assert available_states == [True]


async def test_stream_timeout_after_stop(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_component,
    stream_worker_sync,
    h264_video,
) -> None:
    """Test hls stream timeout after the stream has been stopped already."""
    stream_worker_sync.pause()

    # Setup demo HLS track
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())

    # Request stream
    stream.add_provider(HLS_PROVIDER)
    await stream.start()

    stream_worker_sync.resume()
    await stream.stop()

    # Wait 5 minutes and fire callback.  Stream should already have been
    # stopped so this is a no-op.
    future = dt_util.utcnow() + timedelta(minutes=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("exception"),
    [
        # pylint: disable-next=c-extension-no-member
        (av.error.InvalidDataError(-2, "error")),
        (av.HTTPBadRequestError(500, "error")),
    ],
)
async def test_stream_retries(
    hass: HomeAssistant,
    setup_component,
    should_retry,
    exception,
) -> None:
    """Test hls stream is retried on failure."""
    # Setup demo HLS track
    source = "test_stream_keepalive_source"
    stream = create_stream(hass, source, {}, dynamic_stream_settings())
    track = stream.add_provider(HLS_PROVIDER)
    track.num_segments = 2

    available_states = []

    def update_callback() -> None:
        nonlocal available_states
        available_states.append(stream.available)

    stream.set_update_callback(update_callback)

    open_future1 = hass.loop.create_future()
    open_future2 = hass.loop.create_future()
    futures = [open_future2, open_future1]

    original_set_state = Stream._set_state

    def set_state_wrapper(self, state: bool) -> None:
        if state is False:
            should_retry.return_value = False  # Thread should exit and be joinable.
        original_set_state(self, state)

    def av_open_side_effect(*args, **kwargs):
        hass.loop.call_soon_threadsafe(futures.pop().set_result, None)
        raise exception

    with (
        patch("av.open") as av_open,
        patch("homeassistant.components.stream.Stream._set_state", set_state_wrapper),
        patch("homeassistant.components.stream.STREAM_RESTART_INCREMENT", 0),
    ):
        av_open.side_effect = av_open_side_effect
        # Request stream. Enable retries which are disabled by default in tests.
        should_retry.return_value = True
        await stream.start()
        # Capture the thread reference before yielding to the event loop, since
        # worker_finished() may clear stream._thread once the worker exits.
        worker_thread = stream._thread
        await open_future1
        await open_future2
        await hass.async_add_executor_job(worker_thread.join)
        assert av_open.call_count == 2
        await hass.async_block_till_done()

    # Stop stream, if it hasn't quit already
    await stream.stop()

    # Stream marked initially available, then marked as failed, then marked available
    # before the final failure that exits the stream.
    assert available_states == [True, False, True]


async def test_hls_playlist_view_no_output(
    hass: HomeAssistant, setup_component, hls_stream
) -> None:
    """Test rendering the hls playlist with no output segments."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    # Fetch playlist
    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_hls_playlist_view(
    hass: HomeAssistant, setup_component, hls_stream, stream_worker_sync
) -> None:
    """Test rendering the hls playlist with 1 and 2 output segments."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)
    for i in range(2):
        segment = Segment(sequence=i, duration=SEGMENT_DURATION)
        hls.put(segment)
    await hass.async_block_till_done()

    hls_client = await hls_stream(stream)

    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.OK
    assert await resp.text() == make_playlist(
        sequence=0, segments=[make_segment(0), make_segment(1)]
    )

    segment = Segment(sequence=2, duration=SEGMENT_DURATION)
    hls.put(segment)
    await hass.async_block_till_done()
    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.OK
    assert await resp.text() == make_playlist(
        sequence=0, segments=[make_segment(0), make_segment(1), make_segment(2)]
    )

    stream_worker_sync.resume()
    await stream.stop()


async def test_hls_max_segments(
    hass: HomeAssistant, setup_component, hls_stream, stream_worker_sync
) -> None:
    """Test hls playlist with more segments than the deque can hold."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    # Produce enough segments to overfill the output buffer by one
    for sequence in range(MAX_SEGMENTS + 1):
        segment = Segment(sequence=sequence, duration=SEGMENT_DURATION)
        hls.put(segment)
        await hass.async_block_till_done()

    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.OK

    # Only NUM_PLAYLIST_SEGMENTS are returned in the playlist.
    start = MAX_SEGMENTS + 1 - NUM_PLAYLIST_SEGMENTS
    segments = [make_segment(sequence) for sequence in range(start, MAX_SEGMENTS + 1)]
    assert await resp.text() == make_playlist(sequence=start, segments=segments)

    # Fetch the actual segments with a fake byte payload
    for segment in hls.get_segments():
        segment.init = INIT_BYTES
        segment.parts = [
            Part(
                duration=SEGMENT_DURATION,
                has_keyframe=True,
                data=FAKE_PAYLOAD,
            )
        ]

    # The segment that fell off the buffer is not accessible
    with patch.object(hls.stream_settings, "hls_part_timeout", 0.1):
        segment_response = await hls_client.get("/segment/0.m4s")
    assert segment_response.status == HTTPStatus.NOT_FOUND

    # However all segments in the buffer are accessible,
    # even those that were not in the playlist.
    for sequence in range(1, MAX_SEGMENTS + 1):
        segment_response = await hls_client.get(f"/segment/{sequence}.m4s")
        assert segment_response.status == HTTPStatus.OK

    stream_worker_sync.resume()
    await stream.stop()


async def test_hls_playlist_view_discontinuity(
    hass: HomeAssistant, setup_component, hls_stream, stream_worker_sync
) -> None:
    """Test a discontinuity across segments in the stream with 3 segments."""

    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)

    segment = Segment(sequence=0, stream_id=0, duration=SEGMENT_DURATION)
    hls.put(segment)
    segment = Segment(sequence=1, stream_id=0, duration=SEGMENT_DURATION)
    hls.put(segment)
    segment = Segment(
        sequence=2,
        stream_id=1,
        duration=SEGMENT_DURATION,
    )
    hls.put(segment)
    await hass.async_block_till_done()

    hls_client = await hls_stream(stream)

    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.OK
    assert await resp.text() == make_playlist(
        sequence=0,
        segments=[
            make_segment(0),
            make_segment(1),
            make_segment(2, discontinuity=True),
        ],
    )

    stream_worker_sync.resume()
    await stream.stop()


async def test_hls_max_segments_discontinuity(
    hass: HomeAssistant, setup_component, hls_stream, stream_worker_sync
) -> None:
    """Test a discontinuity with more segments than the segment deque can hold."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)

    hls_client = await hls_stream(stream)

    segment = Segment(sequence=0, stream_id=0, duration=SEGMENT_DURATION)
    hls.put(segment)

    # Produce enough segments to overfill the output buffer by one
    for sequence in range(MAX_SEGMENTS + 1):
        segment = Segment(
            sequence=sequence,
            stream_id=1,
            duration=SEGMENT_DURATION,
        )
        hls.put(segment)
    await hass.async_block_till_done()

    resp = await hls_client.get("/playlist.m3u8")
    assert resp.status == HTTPStatus.OK

    # Only NUM_PLAYLIST_SEGMENTS are returned in the playlist causing the
    # EXT-X-DISCONTINUITY tag to be omitted and EXT-X-DISCONTINUITY-SEQUENCE
    # returned instead.
    start = MAX_SEGMENTS + 1 - NUM_PLAYLIST_SEGMENTS
    segments = [make_segment(sequence) for sequence in range(start, MAX_SEGMENTS + 1)]
    assert await resp.text() == make_playlist(
        sequence=start,
        discontinuity_sequence=1,
        segments=segments,
    )

    stream_worker_sync.resume()
    await stream.stop()


async def test_remove_incomplete_segment_on_exit(
    hass: HomeAssistant, setup_component, stream_worker_sync
) -> None:
    """Test that the incomplete segment gets removed when the worker thread quits."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    await stream.start()
    hls = stream.add_provider(HLS_PROVIDER)

    segment = Segment(sequence=0, stream_id=0, duration=SEGMENT_DURATION)
    hls.put(segment)
    segment = Segment(sequence=1, stream_id=0, duration=SEGMENT_DURATION)
    hls.put(segment)
    segment = Segment(sequence=2, stream_id=0, duration=0)
    hls.put(segment)
    await hass.async_block_till_done()

    segments = hls._segments
    assert len(segments) == 3
    assert not segments[-1].complete
    stream_worker_sync.resume()
    with patch("homeassistant.components.stream.Stream.remove_provider"):
        # Patch remove_provider so the deque is not cleared
        stream._thread_quit.set()
        stream._thread.join()
        stream._thread = None
        await hass.async_block_till_done()
        assert segments[-1].complete
        assert len(segments) == 2
    await stream.stop()


async def test_hls_stream_rotate(
    hass: HomeAssistant, setup_component, hls_stream, stream_worker_sync, h264_video
) -> None:
    """Test hls stream with rotation applied.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """

    stream_worker_sync.pause()

    # Setup demo HLS track
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())

    # Request stream
    stream.add_provider(HLS_PROVIDER)
    await stream.start()

    hls_client = await hls_stream(stream)

    # Fetch master playlist
    master_playlist_response = await hls_client.get()
    assert master_playlist_response.status == HTTPStatus.OK

    # Fetch rotated init
    stream.dynamic_stream_settings.orientation = Orientation.ROTATE_LEFT
    init_response = await hls_client.get("/init.mp4")
    assert init_response.status == HTTPStatus.OK
    init = await init_response.read()

    stream_worker_sync.resume()

    assert_mp4_has_transform_matrix(init, stream.dynamic_stream_settings.orientation)

    # Stop stream, if it hasn't quit already
    await stream.stop()


async def test_hksv_output_coexists_with_hls(
    hass: HomeAssistant, setup_component, stream_worker_sync, h264_video
) -> None:
    """A real stream fans out to both outputs and HKSV close leaves HLS."""
    stream_worker_sync.pause()
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
    hls = stream.add_provider(HLS_PROVIDER)
    camera = Mock(async_create_stream=AsyncMock(return_value=stream))
    try:
        with patch(
            "homeassistant.components.homekit.hksv_stream.get_camera_from_entity_id",
            return_value=camera,
        ):
            shared = await SharedCameraStream.open(hass, "camera.test")
        async with asyncio.timeout(5):
            while not shared.snapshot():
                await hls.recv()
        assert shared.snapshot()
        assert hls.get_segments()
        await shared.close()
        assert stream.outputs()[HLS_PROVIDER] is hls
        assert "homekit_secure_video" not in stream.outputs()
    finally:
        stream_worker_sync.resume()
        await stream.stop()


async def test_hksv_audio_with_hls(
    hass: HomeAssistant, setup_component, stream_worker_sync, tmp_path: Path
) -> None:
    """One real worker sends AAC-converted source audio to both outputs."""
    if not (ffmpeg := shutil.which("ffmpeg")):
        pytest.skip("ffmpeg unavailable")
    path = tmp_path / "source.mkv"
    result = await hass.async_add_executor_job(
        lambda: subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=320x240:rate=15",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:sample_rate=8000",
                "-t",
                "15",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-g",
                "30",
                "-c:a",
                "pcm_alaw",
                "-f",
                "matroska",
                "-y",
                str(path),
            ],
            capture_output=True,
            check=False,
        )
    )
    if result.returncode:
        pytest.skip("ffmpeg test encoders unavailable")
    stream_worker_sync.pause()
    stream = create_stream(hass, str(path), {}, dynamic_stream_settings())
    hls = stream.add_provider(HLS_PROVIDER)
    camera = Mock(async_create_stream=AsyncMock(return_value=stream))
    try:
        with patch(
            "homeassistant.components.homekit.hksv_stream.get_camera_from_entity_id",
            return_value=camera,
        ):
            shared = await SharedCameraStream.open(hass, "camera.test")
        async with asyncio.timeout(5):
            while not shared.snapshot():
                await hls.recv()
        fragment = shared.snapshot()[0]
        with av.open(
            BytesIO(fragment.initialization + fragment.data), format="mp4"
        ) as media:
            assert media.streams.audio[0].codec_context.name == "aac"
        assert any(s.complete for s in hls.get_segments())
        await shared.close()
        assert stream.outputs()[HLS_PROVIDER] is hls
    finally:
        stream_worker_sync.resume()
        await stream.stop()


async def test_hksv_audio_activation_restarts_hls_generation(
    hass: HomeAssistant, setup_component, stream_worker_sync, h264_video
) -> None:
    """Attaching audio to an existing worker creates a new shared generation."""
    stream_worker_sync.pause()
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
    hls = stream.add_provider(HLS_PROVIDER)
    await stream.start()
    camera = Mock(async_create_stream=AsyncMock(return_value=stream))
    try:
        async with asyncio.timeout(5):
            while not hls.get_segments():
                await asyncio.sleep(0.01)
        original_generation = hls.get_segments()[-1].stream_id
        with patch(
            "homeassistant.components.homekit.hksv_stream.get_camera_from_entity_id",
            return_value=camera,
        ):
            shared = await SharedCameraStream.open(hass, "camera.test")
        first_event = stream_worker_sync._event
        second_event = Event()
        stream_worker_sync._event = second_event
        first_event.set()
        async with asyncio.timeout(5):
            while not shared.snapshot():
                await asyncio.sleep(0.01)
        assert shared.snapshot()[0].stream_id > original_generation
        await shared.close()
        assert stream.outputs()[HLS_PROVIDER] is hls
    finally:
        stream_worker_sync.resume()
        await stream.stop()


async def test_one_stream_fans_out_to_recording_and_live(
    hass: HomeAssistant, setup_component, stream_worker_sync, h264_video
) -> None:
    """Three references retain one real worker and release it independently."""
    stream_worker_sync.pause()
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
    camera = Mock(async_create_stream=AsyncMock(return_value=stream))
    leases = []
    try:
        with patch(
            "homeassistant.components.homekit.hksv_stream.get_camera_from_entity_id",
            return_value=camera,
        ):
            leases = await asyncio.gather(
                SharedCameraStream.open(hass, "camera.one"),
                SharedCameraStream.open(hass, "camera.one"),
                SharedCameraStream.open(hass, "camera.one"),
            )
        assert camera.async_create_stream.await_count == 1
        assert list(stream.outputs()) == ["homekit_secure_video"]
        live = leases[1].live_parts()
        async with asyncio.timeout(5):
            init = await anext(live)
            part = await anext(live)
        with av.open(BytesIO(init + part), format="mp4") as media:
            assert media.streams.video[0].codec_context.name == "h264"
        async with asyncio.timeout(5):
            while not leases[0].snapshot():
                await asyncio.sleep(0.01)
        await leases[0].close()
        assert "homekit_secure_video" in stream.outputs()
        async with asyncio.timeout(5):
            assert await anext(live)
        await leases[1].close()
        assert "homekit_secure_video" in stream.outputs()
        stream_worker_sync.resume()
        await leases[2].close()
        assert "homekit_secure_video" not in stream.outputs()
        await live.aclose()
    finally:
        for lease in leases:
            await lease.close()
        stream_worker_sync.resume()
        await stream.stop()


async def test_shared_stream_reconnect_requires_new_live_session_and_fresh_snapshot(
    hass: HomeAssistant, setup_component, stream_worker_sync, h264_video
) -> None:
    """A real worker restart invalidates live input and yields a fresh new keyframe."""
    stream_worker_sync.pause()
    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
    hls = stream.add_provider(HLS_PROVIDER)
    camera = Mock(async_create_stream=AsyncMock(return_value=stream))
    first_worker_done = Event()
    original_discontinuity = stream_worker_sync.blocking_discontinuity

    def on_discontinuity(state):
        first_worker_done.set()
        original_discontinuity(state)

    try:
        with (
            patch(
                "homeassistant.components.homekit.hksv_stream.get_camera_from_entity_id",
                return_value=camera,
            ),
            patch(
                "homeassistant.components.stream.worker.StreamState.discontinuity",
                new=on_discontinuity,
            ),
        ):
            shared = await SharedCameraStream.open(hass, "camera.reconnect")
            await _test_reconnect(
                shared, stream, hls, stream_worker_sync, first_worker_done
            )
    finally:
        stream_worker_sync.resume()
        await stream.stop()


async def _test_reconnect(shared, stream, hls, stream_worker_sync, first_worker_done):
    snapshot_task = None
    try:
        async with asyncio.timeout(5):
            while not shared.snapshot():
                await hls.recv()
        first_generation = shared.snapshot()[0].stream_id
        old_live = shared.live_parts()
        async with asyncio.timeout(5):
            await anext(old_live)
            await anext(old_live)
        assert await asyncio.to_thread(first_worker_done.wait, 3)
        stream.update_source(stream.source)
        first_event = stream_worker_sync._event
        stream_worker_sync._event = Event()
        snapshot_task = asyncio.create_task(shared.image(320, 240))
        await asyncio.sleep(0)
        first_event.set()
        async with asyncio.timeout(5):
            while (
                not shared.snapshot()
                or shared.snapshot()[0].stream_id == first_generation
            ):
                await asyncio.sleep(0.01)

        async def consume_old():
            async for _ in old_live:
                pass

        with pytest.raises(ValueError, match="generation changed"):
            await asyncio.wait_for(consume_old(), 5)
        async with asyncio.timeout(5):
            jpeg = await snapshot_task
        assert jpeg
        with av.open(BytesIO(jpeg), format="mjpeg") as image:
            frame = next(image.decode(video=0))
            assert (frame.width, frame.height) == (320, 240)
        new_live = shared.live_parts()
        async with asyncio.timeout(5):
            init = await anext(new_live)
            part = await anext(new_live)
        with av.open(BytesIO(init + part), format="mp4") as media:
            assert media.streams.video[0].codec_context.name == "h264"
        await new_live.aclose()
        await old_live.aclose()
        await shared.close()
    finally:
        if snapshot_task and not snapshot_task.done():
            snapshot_task.cancel()
            await asyncio.gather(snapshot_task, return_exceptions=True)

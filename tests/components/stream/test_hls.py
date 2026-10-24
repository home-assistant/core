"""The tests for hls streams."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from http import HTTPStatus
import io
import itertools
import sys
import threading
from unittest.mock import DEFAULT, patch
from urllib.parse import urlparse

import av
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator

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
from homeassistant.components.stream.fmp4utils import find_box
from homeassistant.components.stream.worker import StreamState, hevc_keyframe_format
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    FAKE_TIME,
    DefaultSegment as Segment,
    assert_mp4_has_transform_matrix,
    dynamic_stream_settings,
    generate_video_with_size_change,
)
from .conftest import WorkerSync

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


type HlsStreamFactory = Callable[[Stream], Awaitable[HlsClient]]


@pytest.fixture
def hls_stream(hass: HomeAssistant, hass_client: ClientSessionGenerator):
    """Create test fixture for creating an HLS client for a stream."""

    async def create_client_for_stream(stream):
        http_client = await hass_client()
        parsed_url = urlparse(stream.endpoint_url(HLS_PROVIDER))
        return HlsClient(http_client, parsed_url)

    return create_client_for_stream


def make_segment(segment, discontinuity_sequence=None):
    """Create a playlist response for a segment."""
    response = (
        []
        if discontinuity_sequence is None
        else [
            "#EXT-X-DISCONTINUITY",
            f'#EXT-X-MAP:URI="./init/{discontinuity_sequence}.mp4"',
        ]
    )
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
        f'#EXT-X-MAP:URI="./init/{discontinuity_sequence}.mp4"',
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


BOTH_SIZES = [(480, 320), (640, 480)]
ALWAYS = sys.maxsize


@pytest.mark.parametrize(
    ("encoder", "source_options", "size_errors", "init_sizes", "decoded"),
    [
        # hvc1 keeps parameter sets in the init only
        pytest.param("libx265", {}, 0, BOTH_SIZES, BOTH_SIZES, id="h265"),
        # Keyframes that repeat SPS and PPS only keep the stream's VPS
        pytest.param(
            "libx265",
            {"keyframe_vps": False},
            0,
            BOTH_SIZES,
            BOTH_SIZES,
            id="h265-no-keyframe-vps",
        ),
        # Keyframes that carry no parameter sets until the change
        pytest.param(
            "libx265",
            {"first_size_keyframe_sets": False},
            0,
            BOTH_SIZES,
            BOTH_SIZES,
            id="h265-sets-first-in-band-at-change",
        ),
        # Keyframes that repeat some of the stream's parameter sets
        pytest.param(
            "libx265",
            {"extra_pps": True},
            0,
            BOTH_SIZES,
            BOTH_SIZES,
            id="h265-extra-pps",
        ),
        # Parameter sets that do not parse keep the current init
        pytest.param(
            "libx265", {}, ALWAYS, [(480, 320)], [(480, 320)], id="h265-unparsed"
        ),
        # and are tried again on the next keyframe
        pytest.param("libx265", {}, 1, BOTH_SIZES, BOTH_SIZES, id="h265-unparsed-once"),
        # A change at DTS 0, after negative timestamps
        pytest.param(
            "libx265",
            {"change_at_dts_zero": True},
            0,
            BOTH_SIZES,
            BOTH_SIZES,
            id="h265-change-at-dts-zero",
        ),
        # Extradata that differs from the first keyframe's parameter sets
        pytest.param(
            "libx265",
            {"stale_extradata": True},
            0,
            BOTH_SIZES,
            BOTH_SIZES,
            id="h265-stale-extradata",
        ),
        # A new size under a new SPS ID; the old SPS stays in the init
        pytest.param(
            "libx265",
            {"sps_id_switch": True},
            0,
            BOTH_SIZES,
            BOTH_SIZES,
            id="h265-sps-id-switch",
        ),
        # A 4:3 sample aspect ratio that the second size drops
        pytest.param(
            "libx265",
            {"first_size_sar": 14},
            0,
            BOTH_SIZES,
            BOTH_SIZES,
            id="h265-aspect-ratio-change",
        ),
        # avc1 samples keep their in-band parameter sets
        pytest.param("libx264", {}, 0, [(480, 320)], BOTH_SIZES, id="h264"),
    ],
)
@pytest.mark.usefixtures("setup_component")
async def test_hls_stream_picture_size_change(
    hass: HomeAssistant,
    hls_stream: HlsStreamFactory,
    encoder: str,
    source_options: dict[str, bool | int],
    size_errors: int,
    init_sizes: list[tuple[int, int]],
    decoded: list[tuple[int, int]],
) -> None:
    """Test that every playlist segment decodes with its init after a size change."""
    # The change falls 1 s into a segment, so it cuts that segment short
    source = generate_video_with_size_change(
        encoder, BOTH_SIZES, duration=5, **source_options
    )

    # Hold the worker at the end of the stream so the segments stay available
    worker_ended = threading.Event()
    release_worker = threading.Event()
    discontinuity = StreamState.discontinuity

    def hold_worker(stream_state: StreamState) -> None:
        worker_ended.set()
        release_worker.wait()
        discontinuity(stream_state)

    with (
        patch.object(
            StreamState, "discontinuity", autospec=True, side_effect=hold_worker
        ),
        # The first `size_errors` parameter set changes do not decode
        patch(
            "homeassistant.components.stream.worker.hevc_keyframe_format",
            wraps=hevc_keyframe_format,
            side_effect=itertools.chain(
                itertools.repeat(
                    av.FFmpegError(1094995529, "Invalid data"), size_errors
                ),
                itertools.repeat(DEFAULT),
            ),
        ),
    ):
        stream = create_stream(hass, source, {}, dynamic_stream_settings())
        stream.add_provider(HLS_PROVIDER)
        try:
            await stream.start()
            assert await hass.async_add_executor_job(worker_ended.wait, TEST_TIMEOUT)
            await hass.async_block_till_done()

            playlist, inits, decoded_sizes = await decode_playlist(
                await hls_stream(stream)
            )
        finally:
            release_worker.set()
            await stream.stop()

    # Every frame decodes at its source size, in source order
    assert [size for size, _ in itertools.groupby(decoded_sizes)] == decoded
    assert [init_size(init) for init in inits.values()] == init_sizes
    # One discontinuity sequence per size
    assert list(inits) == [f"./init/{index}.mp4" for index in range(len(init_sizes))]
    assert playlist.count("#EXT-X-DISCONTINUITY") == len(init_sizes) - 1


async def decode_playlist(
    hls_client: HlsClient,
) -> tuple[list[str], dict[str, bytes], list[tuple[int, int]]]:
    """Decode each playlist segment with the init its EXT-X-MAP names.

    Return the playlist lines, the inits by URI and the decoded frame sizes.
    """
    playlist_response = await hls_client.get("/playlist.m3u8")
    assert playlist_response.status == HTTPStatus.OK
    playlist = (await playlist_response.text()).splitlines()
    inits: dict[str, bytes] = {}
    init_uri = ""
    decoded_sizes: list[tuple[int, int]] = []
    for line in playlist:
        if line.startswith("#EXT-X-MAP:URI="):
            init_uri = line.removeprefix("#EXT-X-MAP:URI=").strip('"')
            init_response = await hls_client.get("/" + init_uri.removeprefix("./"))
            assert init_response.status == HTTPStatus.OK
            inits[init_uri] = await init_response.read()
        elif line and not line.startswith("#"):
            segment_response = await hls_client.get("/" + line.removeprefix("./"))
            assert segment_response.status == HTTPStatus.OK
            data = inits[init_uri] + await segment_response.read()
            with av.open(io.BytesIO(data)) as container:
                video = container.streams.video[0]
                decoded_sizes.extend(
                    (frame.width, frame.height) for frame in container.decode(video=0)
                )
                # The init's aspect ratio is the one of the SPS in use
                assert (
                    video.sample_aspect_ratio == video.codec_context.sample_aspect_ratio
                )
    return playlist, inits, decoded_sizes


def init_size(init: bytes) -> tuple[int, int]:
    """Return the track size (tkhd width and height) an init declares."""
    moov = next(find_box(init, b"moov"))
    tkhd = next(find_box(init, b"tkhd", next(find_box(init, b"trak", moov))))
    tkhd_end = tkhd + int.from_bytes(init[tkhd : tkhd + 4], byteorder="big")
    # width and height are the last two 16.16 fixed point fields
    return (
        int.from_bytes(init[tkhd_end - 8 : tkhd_end - 6], byteorder="big"),
        int.from_bytes(init[tkhd_end - 4 : tkhd_end - 2], byteorder="big"),
    )


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


@pytest.mark.usefixtures("setup_component")
async def test_hls_playlist_target_duration_short_segment(
    hass: HomeAssistant,
    hls_stream: HlsStreamFactory,
    stream_worker_sync: WorkerSync,
) -> None:
    """Test the target duration after a segment shorter than the minimum."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)
    try:
        # A segment cut early at a parameter set change, then one in progress
        hls.put(Segment(sequence=0, stream_id=0, duration=0.25))
        hls.put(Segment(sequence=1, stream_id=1))
        await hass.async_block_till_done()

        hls_client = await hls_stream(stream)
        resp = await hls_client.get("/playlist.m3u8")
        assert resp.status == HTTPStatus.OK
        playlist = (await resp.text()).splitlines()
    finally:
        stream_worker_sync.resume()
        await stream.stop()

    min_segment_duration = hls.stream_settings.min_segment_duration
    assert f"#EXT-X-TARGETDURATION:{min_segment_duration:.0f}" in playlist


@pytest.mark.parametrize(
    ("segments", "bit_rate"),
    [
        # A segment cut at a parameter set change holds little more than a
        # keyframe; it counts together with the segment before it
        pytest.param([(2.0, 2000), (0.05, 500)], 2516 * 8 / 2.05, id="short-segment"),
        # The peak, not the average over the buffer
        pytest.param(
            [(2.0, 250_000), (2.0, 250_000), (2.0, 250_000), (2.0, 2_000_000)],
            2_000_008 * 8 / 2.0,
            id="bit-rate-increase",
        ),
        # An earlier peak after the bit rate drops
        pytest.param(
            [(2.0, 2_000_000), (2.0, 250_000)],
            2_000_008 * 8 / 2.0,
            id="bit-rate-decrease",
        ),
        # Contiguous segments lasting more than 1.5 target durations do not count
        pytest.param(
            [(0.8, 1_000_000), (2.0, 1000), (0.8, 1_000_000)],
            1_001_016 * 8 / 2.8,
            id="window-too-long",
        ),
        # A segment of half the target duration counts on its own
        pytest.param([(2.0, 1000), (1.0, 1000)], 1008 * 8 / 1.0, id="half-target"),
        # No segments as long as half the target duration: all of them count
        pytest.param(
            [(0.05, 500), (0.05, 1500)], 2016 * 8 / 0.1, id="only-short-segments"
        ),
    ],
)
@pytest.mark.usefixtures("setup_component")
async def test_hls_master_playlist_bandwidth(
    hass: HomeAssistant,
    hls_stream: HlsStreamFactory,
    stream_worker_sync: WorkerSync,
    segments: list[tuple[float, int]],
    bit_rate: float,
) -> None:
    """Test the master playlist bandwidth is the peak bit rate plus 20 %."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)
    try:
        # Complete segments, then one in progress
        for sequence, (duration, size) in enumerate([*segments, (0, 0)]):
            segment = Segment(sequence=sequence, init=INIT_BYTES)
            segment.parts = [Part(duration, has_keyframe=True, data=bytes(size))]
            segment.duration = duration
            hls.put(segment)
        await hass.async_block_till_done()

        hls_client = await hls_stream(stream)
        with patch(
            "homeassistant.components.stream.hls.get_codec_string",
            return_value="hvc1.1.6.L93.B0",
        ):
            resp = await hls_client.get()
        assert resp.status == HTTPStatus.OK
        master_playlist = await resp.text()
    finally:
        stream_worker_sync.resume()
        await stream.stop()

    assert f"#EXT-X-STREAM-INF:BANDWIDTH={round(bit_rate * 1.2)}," in master_playlist


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
    try:
        segment = Segment(
            sequence=0, stream_id=0, init=b"init-0", duration=SEGMENT_DURATION
        )
        hls.put(segment)
        segment = Segment(
            sequence=1, stream_id=0, init=b"init-0", duration=SEGMENT_DURATION
        )
        hls.put(segment)
        segment = Segment(
            sequence=2,
            stream_id=1,
            init=b"init-1",
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
                make_segment(2, discontinuity_sequence=1),
            ],
        )

        # Each discontinuity sequence number serves its own init
        for path, init in (
            ("/init/0.mp4", b"init-0"),
            ("/init/1.mp4", b"init-1"),
            ("/init.mp4", b"init-0"),
        ):
            resp = await hls_client.get(path)
            assert resp.status == HTTPStatus.OK
            assert await resp.read() == init
        resp = await hls_client.get("/init/2.mp4")
        assert resp.status == HTTPStatus.NOT_FOUND
    finally:
        stream_worker_sync.resume()
        await stream.stop()


@pytest.mark.usefixtures("setup_component")
async def test_hls_playlist_view_discontinuity_first_segment(
    hass: HomeAssistant,
    hls_stream: HlsStreamFactory,
    stream_worker_sync: WorkerSync,
) -> None:
    """Test a discontinuity segment that becomes the first playlist segment."""
    stream = create_stream(hass, STREAM_SOURCE, {}, dynamic_stream_settings())
    stream_worker_sync.pause()
    hls = stream.add_provider(HLS_PROVIDER)
    try:
        hls.put(Segment(sequence=0, stream_id=0, duration=SEGMENT_DURATION))
        hls.put(Segment(sequence=1, stream_id=1, duration=SEGMENT_DURATION))
        await hass.async_block_till_done()

        hls_client = await hls_stream(stream)

        # Rendered behind a segment of the previous discontinuity sequence
        resp = await hls_client.get("/playlist.m3u8")
        assert resp.status == HTTPStatus.OK
        assert await resp.text() == make_playlist(
            sequence=0,
            segments=[make_segment(0), make_segment(1, discontinuity_sequence=1)],
        )

        for sequence in range(2, NUM_PLAYLIST_SEGMENTS + 1):
            hls.put(Segment(sequence=sequence, stream_id=1, duration=SEGMENT_DURATION))
        await hass.async_block_till_done()

        # EXT-X-DISCONTINUITY-SEQUENCE counts the discontinuity that left the window
        resp = await hls_client.get("/playlist.m3u8")
        assert resp.status == HTTPStatus.OK
        assert await resp.text() == make_playlist(
            sequence=1,
            discontinuity_sequence=1,
            segments=[
                make_segment(sequence)
                for sequence in range(1, NUM_PLAYLIST_SEGMENTS + 1)
            ],
        )
    finally:
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

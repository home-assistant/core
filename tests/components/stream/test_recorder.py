"""The tests for recording streams."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from functools import partial
from io import BytesIO
import itertools
import os
from pathlib import Path
from unittest.mock import Mock, patch

import av
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.stream import Stream, create_stream
from homeassistant.components.stream.const import (
    ATTR_SETTINGS,
    DOMAIN,
    HLS_PROVIDER,
    OUTPUT_IDLE_TIMEOUT,
    RECORDER_PROVIDER,
)
from homeassistant.components.stream.core import (
    Orientation,
    Part,
    Segment as StreamSegment,
)
from homeassistant.components.stream.fmp4utils import find_box
from homeassistant.components.stream.recorder import RecorderOutput
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    AUDIO_SAMPLE_RATE,
    DefaultSegment as Segment,
    assert_mp4_has_transform_matrix,
    dynamic_stream_settings,
    generate_audio_frame,
    generate_h264_video,
    generate_h265_video,
    generate_video,
    generate_video_with_size_change,
    remux_with_audio,
)


@pytest.fixture(autouse=True)
async def stream_component(hass: HomeAssistant) -> None:
    """Set up the component before each test."""
    await async_setup_component(hass, DOMAIN, {"stream": {}})


@pytest.fixture
def filename(tmp_path: Path) -> str:
    """Use this filename for the tests."""
    return str(tmp_path / "test.mp4")


async def test_record_stream(hass: HomeAssistant, filename, h264_video) -> None:
    """Test record stream."""

    worker_finished = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch remove_provider."""

        async def remove_provider(self, provider):
            """Add a finished event to Stream.remove_provider."""
            await Stream.remove_provider(self, provider)
            worker_finished.set()

    with patch("homeassistant.components.stream.Stream", wraps=MockStream):
        stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        make_recording = hass.async_create_task(stream.async_record(filename))

        # In general usage the recorder will only include what has already been
        # processed by the worker. To guarantee we have some output for the test,
        # wait until the worker has finished before firing
        await worker_finished.wait()

        # Fire the IdleTimer
        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)

        await make_recording

    # Assert
    assert os.path.exists(filename)


@pytest.mark.parametrize(
    "generate_source",
    [
        pytest.param(partial(generate_h264_video, "mpegts", 5), id="h264-b-frames"),
        pytest.param(partial(generate_h265_video, "mpegts", 5), id="h265-b-frames"),
    ],
)
async def test_record_stream_worker_restart(
    hass: HomeAssistant,
    filename: str,
    tmp_path: Path,
    should_retry: Mock,
    generate_source: Callable[[], BytesIO],
) -> None:
    """Test a recording continues across a worker restart.

    The source has video only, with B-frames.
    """
    worker_finished = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch remove_provider."""

        async def remove_provider(self, provider):
            """Add a finished event to Stream.remove_provider."""
            await Stream.remove_provider(self, provider)
            worker_finished.set()

    source = tmp_path / "source.ts"
    source.write_bytes((await hass.async_add_executor_job(generate_source)).getvalue())
    # The worker runs twice over the source, each run in several segments
    should_retry.side_effect = [True, False]
    with (
        patch("homeassistant.components.stream.Stream", wraps=MockStream),
        patch("homeassistant.components.stream.STREAM_RESTART_INCREMENT", 0),
        patch.object(hass.data[DOMAIN][ATTR_SETTINGS], "min_segment_duration", 1.9),
    ):
        stream = create_stream(hass, str(source), {}, dynamic_stream_settings())

        with patch.object(hass.config, "is_allowed_path", return_value=True):
            make_recording = hass.async_create_task(stream.async_record(filename))
            await worker_finished.wait()

            # Fire the IdleTimer
            future = dt_util.utcnow() + timedelta(seconds=30)
            async_fire_time_changed(hass, future)

            await make_recording

    with av.open(filename) as recording:
        assert recording.duration / av.time_base > 5
        dts = [packet.dts for packet in recording.demux(video=0) if packet.size]
    assert all(later > earlier for earlier, later in itertools.pairwise(dts))


async def test_record_stream_h265_is_hvc1(hass: HomeAssistant, filename: str) -> None:
    """Test a h265 recording gets muxed as hvc1, so Apple devices can play it."""
    worker_finished = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch remove_provider."""

        async def remove_provider(self, provider):
            """Add a finished event to Stream.remove_provider."""
            await Stream.remove_provider(self, provider)
            worker_finished.set()

    source = await hass.async_add_executor_job(generate_h265_video)
    with patch("homeassistant.components.stream.Stream", wraps=MockStream):
        stream = create_stream(hass, source, {}, dynamic_stream_settings())

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        make_recording = hass.async_create_task(stream.async_record(filename))
        await worker_finished.wait()

        # Fire the IdleTimer
        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)

        await make_recording

    with av.open(filename) as recording:
        assert recording.streams.video[0].codec_tag == "hvc1"


SIZE_CHANGE = partial(
    generate_video_with_size_change, "libx265", [(480, 320), (640, 480)], 3
)


# Keyframes at least every half second; the segments' first frames have
# different composition offsets once read back
H264_B_FRAMES = partial(
    generate_video, "libx264", "mpegts", 6, options={"g": "12", "keyint_min": "12"}
)


def generate_h264_with_audio() -> BytesIO:
    """Generate an MPEG-TS with B-frames and AAC audio.

    The audio frames (1024 samples, the first one before the video) do not
    line up with the keyframes.
    """
    video_source = av.open(H264_B_FRAMES())
    video_packets = [
        packet for packet in video_source.demux(video=0) if packet.dts is not None
    ]
    output = BytesIO()
    container = av.open(output, mode="w", format="mpegts")
    video_stream = container.add_stream_from_template(video_source.streams.video[0])
    audio_stream = container.add_stream("aac", AUDIO_SAMPLE_RATE)
    audio_packets = []
    for index in range(round(6 * AUDIO_SAMPLE_RATE / 1024)):
        frame = generate_audio_frame()
        frame.pts = index * 1024
        audio_packets.extend(audio_stream.encode(frame))
    audio_packets.extend(audio_stream.encode(None))
    start = video_packets[0].dts * video_packets[0].time_base
    for packet in video_packets:
        packet.stream = video_stream
    for packet in audio_packets:
        packet.pts = packet.dts = packet.pts + round(start / packet.time_base)
        packet.stream = audio_stream
    for packet in sorted(
        video_packets + audio_packets, key=lambda packet: packet.dts * packet.time_base
    ):
        container.mux(packet)
    container.close()
    video_source.close()
    output.seek(0)
    return output


def put_from_sequence(
    first_sequence: int,
) -> Callable[[RecorderOutput, StreamSegment], None]:
    """Return a RecorderOutput.put that drops the segments before first_sequence."""
    put = RecorderOutput.put

    def put_segment(output: RecorderOutput, segment: StreamSegment) -> None:
        if segment.sequence >= first_sequence:
            put(output, segment)

    return put_segment


def recording_offsets(
    source: bytes, recording: str
) -> tuple[set[tuple[float, float]], list[float]]:
    """Return how far the recording moved the source's video, in seconds.

    The recorded video frames are matched to the source frames from the
    source keyframe whose following frames have the same PTS - DTS. The set
    holds the (PTS, DTS) offsets of the matched frames after the first one,
    whose PTS the worker may change. The list holds the recorded audio times
    that are not a source audio time moved by the first of those offsets.
    """
    timestamps = []
    for data in (BytesIO(source), recording):
        with av.open(data) as container:
            timestamps.append(
                [
                    (
                        packet.stream.type,
                        packet.is_keyframe,
                        packet.pts * packet.time_base,
                        packet.dts * packet.time_base,
                    )
                    for packet in container.demux()
                    if packet.size
                ]
            )
    source_video, recorded_video = (
        [packet[1:] for packet in packets if packet[0] == "video"]
        for packets in timestamps
    )
    source_audio, recorded_audio = (
        [pts for kind, _, pts, _ in packets if kind == "audio"]
        for packets in timestamps
    )
    window = len(recorded_video) - 1
    pattern = [pts - dts for _, pts, dts in recorded_video[1:]]
    start = next(
        (
            index
            for index, (key, _, _) in enumerate(source_video)
            if key
            and [
                pts - dts
                for _, pts, dts in source_video[index + 1 : index + 1 + window]
            ]
            == pattern
        ),
        None,
    )
    assert start is not None, "recorded video does not match the source"
    video = {
        (round(float(pts - src_pts), 4), round(float(dts - src_dts), 4))
        for (_, pts, dts), (_, src_pts, src_dts) in zip(
            recorded_video[1:], source_video[start + 1 :], strict=False
        )
    }
    offset = recorded_video[1][1] - source_video[start + 1][1]
    audio = [
        float(pts)
        for pts in recorded_audio
        if not any(abs(pts - offset - src_pts) < 0.001 for src_pts in source_audio)
    ]
    return video, audio


@pytest.mark.parametrize(
    ("generate_source", "min_segment_duration", "first_sequence"),
    [
        pytest.param(SIZE_CHANGE, 5.9, 0, id="h265-size-change"),
        pytest.param(
            partial(SIZE_CHANGE, change_at_dts_zero=True),
            5.9,
            0,
            id="h265-size-change-negative-start",
        ),
        pytest.param(SIZE_CHANGE, 1.9, 0, id="h265-segment-before-size-change"),
        pytest.param(
            partial(SIZE_CHANGE, change_at_dts_zero=True),
            1.9,
            0,
            id="h265-segment-before-size-change-negative-start",
        ),
        pytest.param(H264_B_FRAMES, 0.9, 0, id="h264-b-frames"),
        pytest.param(generate_h264_with_audio, 0.9, 0, id="h264-b-frames-audio"),
        # The first recorded keyframe has a composition offset
        pytest.param(H264_B_FRAMES, 0.9, 1, id="h264-b-frames-later-start"),
        # Audio also starts before the first recorded keyframe
        pytest.param(
            generate_h264_with_audio, 0.9, 1, id="h264-b-frames-audio-later-start"
        ),
    ],
)
async def test_record_stream_decode_times(
    hass: HomeAssistant,
    filename: str,
    generate_source: Callable[[], BytesIO],
    min_segment_duration: float,
    first_sequence: int,
) -> None:
    """Test a recording keeps the source's timestamps across segments.

    The worker gives the first keyframe a PTS equal to its DTS, unlike the
    later keyframes, and a size change starts a new init.
    """
    worker_finished = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch remove_provider."""

        async def remove_provider(self, provider):
            """Add a finished event to Stream.remove_provider."""
            await Stream.remove_provider(self, provider)
            worker_finished.set()

    source = await hass.async_add_executor_job(generate_source)
    source_data = source.getvalue()
    with (
        patch("homeassistant.components.stream.Stream", wraps=MockStream),
        patch.object(
            hass.data[DOMAIN][ATTR_SETTINGS],
            "min_segment_duration",
            min_segment_duration,
        ),
    ):
        stream = create_stream(hass, source, {}, dynamic_stream_settings())

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch.object(RecorderOutput, "put", put_from_sequence(first_sequence)),
    ):
        make_recording = hass.async_create_task(stream.async_record(filename))
        await worker_finished.wait()

        # Fire the IdleTimer
        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)

        await make_recording

    # The recording continues past its first segment
    with av.open(filename) as recording:
        assert recording.start_time == 0
        assert recording.duration / av.time_base > 3
        dts = [packet.dts for packet in recording.demux(video=0) if packet.size]
    # Decode times advance by one frame (24 fps, 90 kHz) across segments
    assert {later - earlier for earlier, later in itertools.pairwise(dts)} == {3750}
    video, audio = await hass.async_add_executor_job(
        recording_offsets, source_data, filename
    )
    # Video presentation and decode times and audio move by one offset
    assert len(video) == 1
    ((offset, dts_offset),) = video
    assert dts_offset == offset
    assert audio == []


async def test_record_lookback(hass: HomeAssistant, filename, h264_video) -> None:
    """Exercise record with lookback."""

    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())

    # Start an HLS feed to enable lookback
    stream.add_provider(HLS_PROVIDER)
    await stream.start()

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await stream.async_record(filename, lookback=4)

    # This test does not need recorder cleanup since it is not fully exercised

    await stream.stop()


async def test_record_path_not_allowed(hass: HomeAssistant, h264_video) -> None:
    """Test where the output path is not allowed by home assistant configuration."""

    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
    with (
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(
            ServiceValidationError,
            match="Cannot write to /example/path because access to this path is not allowed",
        ),
    ):
        await stream.async_record("/example/path")


async def test_record_already_recording(hass: HomeAssistant, h264_video) -> None:
    """Test recording a stream that is already recording."""

    stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
    recorder = stream.add_provider(RECORDER_PROVIDER)
    recorder.video_path = "/example/first.mp4"

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(
            ServiceValidationError,
            match="The stream is already recording to /example/first.mp4",
        ),
    ):
        await stream.async_record("/example/second.mp4")


def add_parts_to_segment(segment, source):
    """Add relevant part data to segment for testing recorder."""
    moof_locs = [*find_box(source.getbuffer(), b"moof"), len(source.getbuffer())]
    segment.init = source.getbuffer()[: moof_locs[0]].tobytes()
    segment.parts = [
        Part(
            duration=None,
            has_keyframe=None,
            data=source.getbuffer()[moof_locs[i] : moof_locs[i + 1]],
        )
        for i in range(len(moof_locs) - 1)
    ]


async def test_recorder_discontinuity(
    hass: HomeAssistant, filename: str, h264_video: BytesIO
) -> None:
    """Test recorder save across a discontinuity."""

    # Run
    # The worker records the PTS - DTS of the first frame, 2 frames in h264_video
    segment_1 = Segment(sequence=1, stream_id=0, video_dts_shift=1024)
    add_parts_to_segment(segment_1, h264_video)
    segment_1.duration = 4
    segment_2 = Segment(sequence=2, stream_id=1, video_dts_shift=1024)
    add_parts_to_segment(segment_2, h264_video)
    segment_2.duration = 4

    provider_ready = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch add_provider."""

        async def start(self):
            """Make Stream.start a noop that gives up async context."""
            await asyncio.sleep(0)

        def add_provider(self, fmt, timeout=OUTPUT_IDLE_TIMEOUT):
            """Add a finished event to Stream.add_provider."""
            provider = Stream.add_provider(self, fmt, timeout)
            provider_ready.set()
            return provider

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("homeassistant.components.stream.Stream", wraps=MockStream),
        patch("homeassistant.components.stream.recorder.RecorderOutput.recv"),
    ):
        stream = create_stream(hass, "blank", {}, dynamic_stream_settings())
        make_recording = hass.async_create_task(stream.async_record(filename))
        await provider_ready.wait()

        recorder_output = stream.outputs()[RECORDER_PROVIDER]
        recorder_output.idle_timer.start()
        recorder_output._segments.extend([segment_1, segment_2])

        # Fire the IdleTimer
        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)

        await make_recording
    # Assert
    assert os.path.exists(filename)
    with av.open(filename) as recording:
        packets = [packet for packet in recording.demux(video=0) if packet.size]
    # Each segment has 5 seconds of frames
    first, second = packets[0], packets[len(packets) // 2]
    assert (second.pts - first.pts) * first.time_base == 5
    assert (second.dts - first.dts) * first.time_base == 5


async def test_recorder_no_segments(hass: HomeAssistant, filename) -> None:
    """Test recorder behavior with a stream failure which causes no segments."""

    stream = create_stream(hass, BytesIO(), {}, dynamic_stream_settings())

    # Run
    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await stream.async_record(filename)

    # Assert
    assert not os.path.exists(filename)


@pytest.fixture(scope="module")
def h264_mov_video():
    """Generate a source video with no audio."""
    return generate_h264_video(container_format="mov")


@pytest.mark.parametrize(
    ("audio_codec", "expected_audio_streams"),
    [
        ("aac", 1),  # aac is a valid mp4 codec
        ("pcm_mulaw", 0),  # G.711 is not a valid mp4 codec
        ("empty", 0),  # audio stream with no packets
        (None, 0),  # no audio stream
    ],
)
async def test_record_stream_audio(
    hass: HomeAssistant,
    filename,
    audio_codec,
    expected_audio_streams,
    h264_mov_video,
) -> None:
    """Test treatment of different audio inputs.

    Record stream output should have an audio channel when input has
    a valid codec and audio packets and no audio channel otherwise.
    """

    # Remux source video with new audio
    source = remux_with_audio(h264_mov_video, "mov", audio_codec)  # mov can store PCM

    worker_finished = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch remove_provider."""

        async def remove_provider(self, provider):
            """Add a finished event to Stream.remove_provider."""
            await Stream.remove_provider(self, provider)
            worker_finished.set()

    with patch("homeassistant.components.stream.Stream", wraps=MockStream):
        stream = create_stream(hass, source, {}, dynamic_stream_settings())

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        make_recording = hass.async_create_task(stream.async_record(filename))

        # In general usage the recorder will only include what has already been
        # processed by the worker. To guarantee we have some output for the test,
        # wait until the worker has finished before firing
        await worker_finished.wait()

        # Fire the IdleTimer
        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        await make_recording

    # Assert
    assert os.path.exists(filename)

    result = av.open(
        filename,
        "r",
        format="mp4",
    )

    assert len(result.streams.audio) == expected_audio_streams
    result.close()
    await stream.stop()
    await hass.async_block_till_done()


async def test_recorder_log(
    hass: HomeAssistant, filename, caplog: pytest.LogCaptureFixture
) -> None:
    """Test starting a stream to record logs the url without username and password."""
    stream = create_stream(
        hass, "https://abcd:efgh@foo.bar", {}, dynamic_stream_settings()
    )
    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await stream.async_record(filename)
    assert "https://abcd:efgh@foo.bar" not in caplog.text
    assert "https://****:****@foo.bar" in caplog.text


async def test_record_stream_rotate(hass: HomeAssistant, filename, h264_video) -> None:
    """Test record stream with rotation."""

    worker_finished = asyncio.Event()

    class MockStream(Stream):
        """Mock Stream so we can patch remove_provider."""

        async def remove_provider(self, provider):
            """Add a finished event to Stream.remove_provider."""
            await Stream.remove_provider(self, provider)
            worker_finished.set()

    with patch("homeassistant.components.stream.Stream", wraps=MockStream):
        stream = create_stream(hass, h264_video, {}, dynamic_stream_settings())
        stream.dynamic_stream_settings.orientation = Orientation.ROTATE_RIGHT

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        make_recording = hass.async_create_task(stream.async_record(filename))

        # In general usage the recorder will only include what has already been
        # processed by the worker. To guarantee we have some output for the test,
        # wait until the worker has finished before firing
        await worker_finished.wait()

        # Fire the IdleTimer
        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)

        await make_recording

    # Assert
    assert os.path.exists(filename)
    data = await hass.async_add_executor_job(Path(filename).read_bytes)
    assert_mp4_has_transform_matrix(data, stream.dynamic_stream_settings.orientation)

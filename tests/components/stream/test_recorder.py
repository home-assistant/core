"""The tests for recording streams."""

import asyncio
from datetime import timedelta
from io import BytesIO
import os
from pathlib import Path
from unittest.mock import patch

import av
import pytest

from homeassistant.components.stream import Stream, create_stream
from homeassistant.components.stream.const import (
    HLS_PROVIDER,
    OUTPUT_IDLE_TIMEOUT,
    RECORDER_PROVIDER,
)
from homeassistant.components.stream.core import Orientation, Part
from homeassistant.components.stream.fmp4utils import find_box
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import (
    DefaultSegment as Segment,
    assert_mp4_has_transform_matrix,
    dynamic_stream_settings,
    generate_h264_video,
    remux_with_audio,
)

from tests.common import async_fire_time_changed


@pytest.fixture(autouse=True)
async def stream_component(hass: HomeAssistant) -> None:
    """Set up the component before each test."""
    await async_setup_component(hass, "stream", {"stream": {}})


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
        pytest.raises(HomeAssistantError),
    ):
        await stream.async_record("/example/path")


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
    hass: HomeAssistant, filename, h264_video
) -> None:
    """Test recorder save across a discontinuity."""

    # Run
    segment_1 = Segment(sequence=1, stream_id=0)
    add_parts_to_segment(segment_1, h264_video)
    segment_1.duration = 4
    segment_2 = Segment(sequence=2, stream_id=1)
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

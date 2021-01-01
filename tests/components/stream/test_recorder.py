"""The tests for hls streams."""
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import av
import pytest

from homeassistant.components.stream.core import Segment
from homeassistant.components.stream.recorder import recorder_save_worker
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.stream.common import generate_h264_video, preload_stream


@pytest.mark.skip("Flaky in CI")
async def test_record_stream(hass, hass_client):
    """
    Test record stream.

    Purposefully not mocking anything here to test full
    integration with the stream component.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    with patch("homeassistant.components.stream.recorder.recorder_save_worker"):
        # Setup demo track
        source = generate_h264_video()
        stream = preload_stream(hass, source)
        recorder = stream.add_provider("recorder")
        stream.start()

        while True:
            segment = await recorder.recv()
            if not segment:
                break
            segments = segment.sequence

        stream.stop()

        assert segments > 1


@pytest.mark.skip("Flaky in CI")
async def test_recorder_timeout(hass, hass_client):
    """Test recorder timeout."""
    await async_setup_component(hass, "stream", {"stream": {}})

    with patch(
        "homeassistant.components.stream.recorder.RecorderOutput.cleanup"
    ) as mock_cleanup:
        # Setup demo track
        source = generate_h264_video()
        stream = preload_stream(hass, source)
        recorder = stream.add_provider("recorder")
        stream.start()

        await recorder.recv()

        # Wait a minute
        future = dt_util.utcnow() + timedelta(minutes=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert mock_cleanup.called


@pytest.mark.skip("Flaky in CI")
async def test_recorder_save():
    """Test recorder save."""
    # Setup
    source = generate_h264_video()
    output = BytesIO()
    output.name = "test.mp4"

    # Run
    recorder_save_worker(output, [Segment(1, source, 4)], "mp4")

    # Assert
    assert output.getvalue()


@pytest.mark.skip("Flaky in CI")
async def test_record_stream_audio(hass, hass_client):
    """
    Test treatment of different audio inputs.

    Record stream output should have an audio channel when input has
    a valid codec and audio packets and no audio channel otherwise.
    """
    await async_setup_component(hass, "stream", {"stream": {}})

    for a_codec, expected_audio_streams in (
        ("aac", 1),  # aac is a valid mp4 codec
        ("pcm_mulaw", 0),  # G.711 is not a valid mp4 codec
        ("empty", 0),  # audio stream with no packets
        (None, 0),  # no audio stream
    ):
        with patch("homeassistant.components.stream.recorder.recorder_save_worker"):
            # Setup demo track
            source = generate_h264_video(
                container_format="mov", audio_codec=a_codec
            )  # mov can store PCM
            stream = preload_stream(hass, source)
            recorder = stream.add_provider("recorder")
            stream.start()

            while True:
                segment = await recorder.recv()
                if not segment:
                    break
                last_segment = segment

            result = av.open(last_segment.segment, "r", format="mp4")

            assert len(result.streams.audio) == expected_audio_streams
            result.close()
            stream.stop()

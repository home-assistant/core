"""The tests for hls streams."""
from datetime import timedelta
from io import BytesIO

import pytest

from homeassistant.components.stream.core import Segment
from homeassistant.components.stream.recorder import recorder_save_worker
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
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

        segments = 0
        while True:
            segment = await recorder.recv()
            if not segment:
                break
            segments += 1

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
    recorder_save_worker(output, [Segment(1, source, 4)])

    # Assert
    assert output.getvalue()

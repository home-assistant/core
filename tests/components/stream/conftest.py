"""Test fixtures for the stream component.

The tests encode stream (as an h264 video), then load the stream and verify
that it is decoded properly. The background worker thread responsible for
decoding will decode the stream as fast as possible, and when completed
clears all output buffers. This can be a problem for the test that wishes
to retrieve and verify decoded segments. If the worker finishes first, there is
nothing for the test to verify. The solution is the WorkerSync class that
allows the tests to pause the worker thread before finalizing the stream
so that it can inspect the output.
"""

import logging
import threading
from unittest.mock import patch

import pytest

from homeassistant.components.stream.core import Segment, StreamOutput


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
            logging.error("blocking worker")
            self._event.wait()

        # Forward to actual StreamOutput.put
        self._put_original(stream_output, segment)


@pytest.fixture()
def stream_worker_sync(hass):
    """Patch StreamOutput to allow test to synchronize worker stream end."""
    sync = WorkerSync()
    with patch(
        "homeassistant.components.stream.core.StreamOutput.put",
        side_effect=sync.blocking_put,
        autospec=True,
    ):
        yield sync

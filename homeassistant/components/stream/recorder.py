"""Provide functionality to record stream."""
from collections import deque
import logging
import os
import threading
from typing import Deque, List

import av

from homeassistant.core import callback

from .const import OUTPUT_CONTAINER_FORMAT
from .core import Segment, StreamOutput

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_recorder(hass):
    """Only here so Provider Registry works."""


def recorder_save_worker(file_out: str, segments: Deque[Segment], container_format):
    """Handle saving stream."""
    if not os.path.exists(os.path.dirname(file_out)):
        os.makedirs(os.path.dirname(file_out), exist_ok=True)

    pts_adjuster = {"video": None, "audio": None}
    output = av.open(file_out, "w", format=container_format)
    output_v = None
    output_a = None

    last_stream_id = None
    running_duration = 0  # the running duration of processed segments

    last_sequence = float("-inf")
    for segment in segments:
        # Because the stream_worker is in a different thread from the record service,
        # the lookback segments may still have some overlap with the recorder segments
        if segment.sequence <= last_sequence:
            continue
        last_sequence = segment.sequence

        # Open segment
        source = av.open(segment.segment, "r", format=container_format)
        source_v = source.streams.video[0]
        source_a = source.streams.audio[0] if len(source.streams.audio) > 0 else None

        # Add output streams if necessary
        if not output_v:
            output_v = output.add_stream(template=source_v)
            context = output_v.codec_context
            context.flags |= "GLOBAL_HEADER"
        if source_a and not output_a:
            output_a = output.add_stream(template=source_a)

        # Recalculate pts adjustments on first segment and on any discontinuity
        # We are assuming time base is the same across all discontinuities
        if last_stream_id != segment.stream_id:
            last_stream_id = segment.stream_id
            pts_adjuster["video"] = running_duration - source_v.start_time
            if source_a:
                pts_adjuster["audio"] = int(
                    (running_duration - source_v.start_time)
                    * source_v.time_base
                    / source_a.time_base
                )

        # Remux video
        for packet in source.demux():
            if packet.dts is None:
                continue
            packet.pts += pts_adjuster[packet.stream.type]
            packet.dts += pts_adjuster[packet.stream.type]
            packet.stream = output_v if packet.stream.type == "video" else output_a
            output.mux(packet)

        running_duration += source_v.duration

        source.close()

    output.close()


class RecorderOutput(StreamOutput):
    """Represents HLS Output formats."""

    def __init__(self, hass) -> None:
        """Initialize recorder output."""
        super().__init__(hass)
        self.video_path = None
        self._segments = deque()

    def _async_put(self, segment: Segment) -> None:
        """Store output."""
        self._segments.append(segment)

    def prepend(self, segments: List[Segment]) -> None:
        """Prepend segments to existing list."""
        self._segments.extendleft(reversed(segments))

    def save(self):
        """Write recording and clean up."""
        _LOGGER.debug("Starting recorder worker thread")
        thread = threading.Thread(
            name="recorder_save_worker",
            target=recorder_save_worker,
            args=(self.video_path, self._segments, OUTPUT_CONTAINER_FORMAT),
        )
        thread.start()
        self._segments = deque()

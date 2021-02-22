"""Provide functionality to record stream."""
import logging
import os
import threading
from typing import Deque, List

import av

from homeassistant.core import HomeAssistant, callback

from .const import RECORDER_CONTAINER_FORMAT, SEGMENT_CONTAINER_FORMAT
from .core import PROVIDERS, IdleTimer, Segment, StreamOutput

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_recorder(hass):
    """Only here so Provider Registry works."""


def recorder_save_worker(file_out: str, segments: Deque[Segment]):
    """Handle saving stream."""
    if not os.path.exists(os.path.dirname(file_out)):
        os.makedirs(os.path.dirname(file_out), exist_ok=True)

    pts_adjuster = {"video": None, "audio": None}
    output = None
    output_v = None
    output_a = None

    last_stream_id = None
    # The running duration of processed segments. Note that this is in av.time_base
    # units which seem to be defined inversely to how stream time_bases are defined
    running_duration = 0

    last_sequence = float("-inf")
    for segment in segments:
        # Because the stream_worker is in a different thread from the record service,
        # the lookback segments may still have some overlap with the recorder segments
        if segment.sequence <= last_sequence:
            continue
        last_sequence = segment.sequence

        # Open segment
        source = av.open(segment.segment, "r", format=SEGMENT_CONTAINER_FORMAT)
        source_v = source.streams.video[0]
        source_a = source.streams.audio[0] if len(source.streams.audio) > 0 else None

        # Create output on first segment
        if not output:
            output = av.open(
                file_out,
                "w",
                format=RECORDER_CONTAINER_FORMAT,
                container_options={
                    "video_track_timescale": str(int(1 / source_v.time_base))
                },
            )

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
            pts_adjuster["video"] = int(
                (running_duration - source.start_time)
                / (av.time_base * source_v.time_base)
            )
            if source_a:
                pts_adjuster["audio"] = int(
                    (running_duration - source.start_time)
                    / (av.time_base * source_a.time_base)
                )

        # Remux video
        for packet in source.demux():
            if packet.dts is None:
                continue
            packet.pts += pts_adjuster[packet.stream.type]
            packet.dts += pts_adjuster[packet.stream.type]
            packet.stream = output_v if packet.stream.type == "video" else output_a
            output.mux(packet)

        running_duration += source.duration - source.start_time

        source.close()

    output.close()


@PROVIDERS.register("recorder")
class RecorderOutput(StreamOutput):
    """Represents HLS Output formats."""

    def __init__(self, hass: HomeAssistant, idle_timer: IdleTimer) -> None:
        """Initialize recorder output."""
        super().__init__(hass, idle_timer)
        self.video_path = None

    @property
    def name(self) -> str:
        """Return provider name."""
        return "recorder"

    def prepend(self, segments: List[Segment]) -> None:
        """Prepend segments to existing list."""
        self._segments.extendleft(reversed(segments))

    def cleanup(self):
        """Write recording and clean up."""
        _LOGGER.debug("Starting recorder worker thread")
        thread = threading.Thread(
            name="recorder_save_worker",
            target=recorder_save_worker,
            args=(self.video_path, self._segments),
        )
        thread.start()

        super().cleanup()

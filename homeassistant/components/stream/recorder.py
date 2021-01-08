"""Provide functionality to record stream."""
import os
import threading
from typing import List

import av

from homeassistant.core import callback

from .core import PROVIDERS, Segment, StreamOutput


@callback
def async_setup_recorder(hass):
    """Only here so Provider Registry works."""


def recorder_save_worker(file_out: str, segments: List[Segment], container_format: str):
    """Handle saving stream."""
    if not os.path.exists(os.path.dirname(file_out)):
        os.makedirs(os.path.dirname(file_out), exist_ok=True)

    first_pts = {"video": None, "audio": None}
    output = av.open(file_out, "w", format=container_format)
    output_v = None
    output_a = None

    # Get first_pts values from first segment
    if len(segments) > 0:
        segment = segments[0]
        source = av.open(segment.segment, "r", format=container_format)
        source_v = source.streams.video[0]
        first_pts["video"] = source_v.start_time
        if len(source.streams.audio) > 0:
            source_a = source.streams.audio[0]
            first_pts["audio"] = int(
                source_v.start_time * source_v.time_base / source_a.time_base
            )
        source.close()

    for segment in segments:
        # Open segment
        source = av.open(segment.segment, "r", format=container_format)
        source_v = source.streams.video[0]
        # Add output streams
        if not output_v:
            output_v = output.add_stream(template=source_v)
            context = output_v.codec_context
            context.flags |= "GLOBAL_HEADER"
        if not output_a and len(source.streams.audio) > 0:
            source_a = source.streams.audio[0]
            output_a = output.add_stream(template=source_a)

        # Remux video
        for packet in source.demux():
            if packet.dts is None:
                continue
            packet.pts -= first_pts[packet.stream.type]
            packet.dts -= first_pts[packet.stream.type]
            packet.stream = output_v if packet.stream.type == "video" else output_a
            output.mux(packet)

        source.close()

    output.close()


@PROVIDERS.register("recorder")
class RecorderOutput(StreamOutput):
    """Represents HLS Output formats."""

    def __init__(self, stream, timeout: int = 30) -> None:
        """Initialize recorder output."""
        super().__init__(stream, timeout)
        self.video_path = None
        self._segments = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return "recorder"

    @property
    def format(self) -> str:
        """Return container format."""
        return "mp4"

    @property
    def audio_codecs(self) -> str:
        """Return desired audio codec."""
        return {"aac", "mp3"}

    @property
    def video_codecs(self) -> tuple:
        """Return desired video codecs."""
        return {"hevc", "h264"}

    def prepend(self, segments: List[Segment]) -> None:
        """Prepend segments to existing list."""
        own_segments = self.segments
        segments = [s for s in segments if s.sequence not in own_segments]
        self._segments = segments + self._segments

    @callback
    def _timeout(self, _now=None):
        """Handle recorder timeout."""
        self._unsub = None
        self.cleanup()

    def cleanup(self):
        """Write recording and clean up."""
        thread = threading.Thread(
            name="recorder_save_worker",
            target=recorder_save_worker,
            args=(self.video_path, self._segments, self.format),
        )
        thread.start()

        self._segments = []
        self._stream.remove_provider(self)

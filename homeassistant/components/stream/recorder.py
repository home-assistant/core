"""Provide functionality to record stream."""
import threading
from typing import List

from homeassistant.core import callback

from .core import Segment, StreamOutput, PROVIDERS


@callback
def async_setup_recorder(hass):
    """Only here so Provider Registry works."""


def recorder_save_worker(file_out: str, segments: List[Segment]):
    """Handle saving stream."""
    import av

    output = av.open(file_out, 'w', options={'movflags': 'frag_keyframe'})
    output_v = None

    for segment in segments:
        # Seek to beginning and open segment
        segment.segment.seek(0)
        source = av.open(segment.segment, 'r', format='mpegts')
        source_v = source.streams.video[0]

        # Add output streams
        if not output_v:
            output_v = output.add_stream(template=source_v)

        # Remux video
        for packet in source.demux(source_v):
            if packet is not None and packet.dts is not None:
                packet.stream = output_v
                output.mux(packet)

    output.close()


@PROVIDERS.register('recorder')
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
        return 'recorder'

    @property
    def format(self) -> str:
        """Return container format."""
        return 'mpegts'

    @property
    def audio_codec(self) -> str:
        """Return desired audio codec."""
        return 'aac'

    @property
    def video_codec(self) -> str:
        """Return desired video codec."""
        return 'h264'

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
            name='recorder_save_worker',
            target=recorder_save_worker,
            args=(self.video_path, self._segments))
        thread.start()

        self._segments = []
        self._stream.remove_provider(self)

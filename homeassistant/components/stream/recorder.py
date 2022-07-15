"""Provide functionality to record stream."""
from __future__ import annotations

from io import BytesIO
import logging
import os

import av

from homeassistant.core import HomeAssistant, callback

from .const import (
    RECORDER_CONTAINER_FORMAT,
    RECORDER_PROVIDER,
    SEGMENT_CONTAINER_FORMAT,
)
from .core import PROVIDERS, IdleTimer, Segment, StreamOutput, StreamSettings

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_recorder(hass: HomeAssistant) -> None:
    """Only here so Provider Registry works."""


@PROVIDERS.register(RECORDER_PROVIDER)
class RecorderOutput(StreamOutput):
    """Represents the Recorder Output format."""

    def __init__(
        self,
        hass: HomeAssistant,
        idle_timer: IdleTimer,
        stream_settings: StreamSettings,
    ) -> None:
        """Initialize recorder output."""
        super().__init__(hass, idle_timer, stream_settings)
        self.video_path: str

    @property
    def name(self) -> str:
        """Return provider name."""
        return RECORDER_PROVIDER

    def prepend(self, segments: list[Segment]) -> None:
        """Prepend segments to existing list."""
        self._segments.extendleft(reversed(segments))

    def cleanup(self) -> None:
        """Handle cleanup."""
        self.idle_timer.idle = True
        super().cleanup()

    async def async_record(self) -> None:
        """Handle saving stream."""

        os.makedirs(os.path.dirname(self.video_path), exist_ok=True)

        pts_adjuster: dict[str, int | None] = {"video": None, "audio": None}
        output: av.container.OutputContainer | None = None
        output_v = None
        output_a = None

        last_stream_id = -1
        # The running duration of processed segments. Note that this is in av.time_base
        # units which seem to be defined inversely to how stream time_bases are defined
        running_duration = 0

        last_sequence = float("-inf")

        def write_segment(segment: Segment) -> None:
            """Write a segment to output."""
            nonlocal output, output_v, output_a, last_stream_id, running_duration, last_sequence
            # Because the stream_worker is in a different thread from the record service,
            # the lookback segments may still have some overlap with the recorder segments
            if segment.sequence <= last_sequence:
                return
            last_sequence = segment.sequence

            # Open segment
            source = av.open(
                BytesIO(segment.init + segment.get_data()),
                "r",
                format=SEGMENT_CONTAINER_FORMAT,
            )
            # Skip this segment if it doesn't have data
            if source.duration is None:
                source.close()
                return
            source_v = source.streams.video[0]
            source_a = (
                source.streams.audio[0] if len(source.streams.audio) > 0 else None
            )

            # Create output on first segment
            if not output:
                output = av.open(
                    self.video_path + ".tmp",
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

        # Write lookback segments
        while len(self._segments) > 1:  # The last segment is in progress
            await self._hass.async_add_executor_job(
                write_segment, self._segments.popleft()
            )
        # Make sure the first segment has been added
        if not self._segments:
            await self.recv()
        # Write segments as soon as they are completed
        while not self.idle:
            await self.recv()
            await self._hass.async_add_executor_job(
                write_segment, self._segments.popleft()
            )
        # Write remaining segments
        # Should only have 0 or 1 segments, but loop through just in case
        while self._segments:
            await self._hass.async_add_executor_job(
                write_segment, self._segments.popleft()
            )
        if output is None:
            _LOGGER.error("Recording failed to capture anything")
        else:
            output.close()
            os.rename(self.video_path + ".tmp", self.video_path)

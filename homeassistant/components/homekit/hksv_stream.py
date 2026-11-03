"""Shared Home Assistant stream output for HKSV fragment inspection.

This adapter only transports fragments. Callers must verify codec and recording
parameters before advertising HKSV or delivering any data.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, cast, override

from homeassistant.components.camera import get_camera_from_entity_id
from homeassistant.components.stream.core import (  # pylint: disable=home-assistant-component-root-import
    PROVIDERS,
    IdleTimer,
    Segment,
    StreamOutput,
    StreamSettings,
)

if TYPE_CHECKING:
    from av.container import InputContainer

    from homeassistant.components.camera import DynamicStreamSettings
    from homeassistant.components.stream import Stream
from homeassistant.core import HomeAssistant, callback

_PROVIDER = "homekit_secure_video"
_MAX_SEGMENTS = 8
_MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
_SHARED_STREAMS = "homekit_shared_camera_streams"


@PROVIDERS.register(_PROVIDER)
class HKSVStreamOutput(StreamOutput):
    """Keep a bounded list of references to the shared stream's segments."""

    requires_aac_audio = False

    def __init__(
        self,
        hass: HomeAssistant,
        idle_timer: IdleTimer,
        stream_settings: StreamSettings,
        dynamic_stream_settings: DynamicStreamSettings,
    ) -> None:
        """Initialize the bounded provider."""
        super().__init__(
            hass,
            idle_timer,
            stream_settings,
            dynamic_stream_settings,
            deque_maxlen=_MAX_SEGMENTS,
        )

    @callback
    def _trim_bytes(self) -> None:
        """Bound retained segment references as their parts arrive."""
        while (
            self._segments
            and sum(s.data_size_with_init for s in self._segments) > _MAX_SNAPSHOT_BYTES
        ):
            self._segments.popleft()

    @callback
    @override
    def _async_put(self, segment: Segment) -> None:
        super()._async_put(segment)
        self._trim_bytes()

    @callback
    @override
    def part_put(self) -> None:
        """Trim references as segment parts arrive."""
        self._trim_bytes()
        super().part_put()

    @property
    @override
    def name(self) -> str:
        """Return the provider name."""
        return _PROVIDER

    @callback
    @override
    def cleanup(self) -> None:
        """Release references and wake waiting consumers."""
        super().cleanup()
        self._segments.clear()


@dataclass(frozen=True, slots=True)
class SharedFragment:
    """One completed segment from a shared stream generation."""

    stream_id: int
    sequence: int
    initialization: bytes
    data: bytes
    duration: float


class _SharedEntry:
    """Serialize acquisition and release across accessories for one entity."""

    def __init__(self, entries: dict[str, _SharedEntry], entity_id: str) -> None:
        """Initialize an empty provider entry."""
        self.lock = asyncio.Lock()
        self.owner: SharedCameraStream | None = None
        self.references = 0
        self.waiters = 0
        self.entries = entries
        self.entity_id = entity_id

    def discard_if_unused(self) -> None:
        """Remove the registry entry only when no owner, lease or opener remains."""
        if (
            self.references == 0
            and self.waiters == 0
            and self.owner is None
            and self.entries.get(self.entity_id) is self
        ):
            del self.entries[self.entity_id]


class SharedCameraStream:
    """Own a dedicated output on a Camera's existing shared stream."""

    def __init__(self, stream: Stream, output: HKSVStreamOutput) -> None:
        """Store the stream and owned output."""
        self._stream = stream
        self._output = output
        self._closed = False
        self._shared_entry: _SharedEntry | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._live_start: tuple[int, int] | None = None
        self.live_initial_burst = 0.0
        self._live_start_ready = asyncio.Event()

    @classmethod
    async def open(
        cls, hass: HomeAssistant, entity_id: str, *, receive_timestamps: bool = False
    ) -> SharedCameraStream:
        """Acquire a reference to the camera's shared output."""
        entries = hass.data.setdefault(_SHARED_STREAMS, {})
        entry = entries.setdefault(entity_id, _SharedEntry(entries, entity_id))
        entry.waiters += 1
        try:
            async with entry.lock:
                if entry.owner is not None and (
                    entry.owner._closed or not entry.owner._attached()  # noqa: SLF001
                ):
                    await entry.owner.close()
                    entry.owner = None
                if entry.owner is None:
                    # Keep audio available for later consumers without reconnecting.
                    entry.owner = await cls._open_owned(
                        hass, entity_id, receive_timestamps=receive_timestamps
                    )
                elif (
                    entry.owner._output.requires_wallclock_timestamps is True  # noqa: SLF001
                ) != receive_timestamps:
                    raise ValueError("Conflicting camera timestamp settings")
                entry.references += 1
                lease = cls(entry.owner._stream, entry.owner._output)  # noqa: SLF001
                lease._shared_entry = entry
                return lease
        finally:
            entry.waiters -= 1
            entry.discard_if_unused()

    @classmethod
    async def _open_owned(
        cls, hass: HomeAssistant, entity_id: str, *, receive_timestamps: bool = False
    ) -> SharedCameraStream:
        """Attach the single shared output to the existing camera worker."""
        camera = get_camera_from_entity_id(hass, entity_id)
        stream = await camera.async_create_stream()
        if stream is None:
            raise ValueError("Camera has no stream")
        if _PROVIDER in stream.outputs():
            raise RuntimeError("Camera already has an HKSV stream owner")
        was_running = stream.is_running
        output = stream.add_provider(_PROVIDER, timeout=300)
        assert isinstance(output, HKSVStreamOutput)
        output.requires_aac_audio = True
        output.requires_wallclock_timestamps = receive_timestamps
        owner = cls(stream, output)
        try:
            if was_running:
                stream.update_source(stream.source)
            await stream.start()
        except BaseException:
            await owner.close()
            raise
        return owner

    def _attached(self) -> bool:
        """Return whether this output is still owned by the camera stream."""
        return self._stream.outputs().get(_PROVIDER) is self._output

    def _check_attached(self) -> None:
        if self._shared_entry is not None and not self._attached():
            raise ValueError("Shared camera output is no longer attached")

    def snapshot(
        self, cursor: tuple[int, int] | None = None, *, include_partial: bool = False
    ) -> tuple[SharedFragment, ...]:
        """Copy bounded keyframe segments; optionally include current partial media."""
        self._check_attached()
        self._output.idle_timer.awake()
        segments = tuple(self._output.get_segments())
        if not segments:
            return ()
        current_id = segments[-1].stream_id
        eligible = tuple(
            s
            for s in segments
            if s.stream_id == current_id
            and (s.complete or include_partial)
            and s.parts
            and s.parts[0].has_keyframe
            and (cursor is None or s.stream_id != cursor[0] or s.sequence > cursor[1])
        )
        if (
            sum(s.data_size for s in eligible)
            + (len(eligible[0].init) if eligible else 0)
            > _MAX_SNAPSHOT_BYTES
        ):
            raise ValueError("HKSV prebuffer exceeds byte limit")
        return tuple(
            SharedFragment(s.stream_id, s.sequence, s.init, s.get_data(), s.duration)
            for s in eligible
        )

    async def fragments(self) -> AsyncIterator[SharedFragment]:
        """Yield each complete segment once, including after stream restarts."""
        cursor: tuple[int, int] | None = None
        while not self._closed:
            for fragment in self.snapshot(cursor):
                if (
                    cursor is not None
                    and fragment.stream_id == cursor[0]
                    and fragment.sequence != cursor[1] + 1
                ):
                    raise ValueError("HKSV consumer missed stream segments")
                cursor = (fragment.stream_id, fragment.sequence)
                yield fragment
            # Parts complete a segment after it was initially published.
            try:
                async with asyncio.timeout(1):
                    await self._output.part_recv()
            except TimeoutError:
                pass

    async def image(self, width: int, height: int) -> bytes | None:
        """Decode a fresh keyframe from the shared source."""
        self._check_attached()
        image = await self._stream.async_get_image(
            width=width,
            height=height,
            wait_for_next_keyframe=True,
            use_existing_stream=True,
            require_fresh=True,
        )
        self._check_attached()
        return image

    async def prepare_live_input(self) -> float:
        """Pin the live start and measure safe initial catch-up credit."""
        self._check_attached()
        segments = tuple(self._output.get_segments())
        segment = next(
            (s for s in reversed(segments) if s.parts and s.parts[0].has_keyframe),
            None,
        )
        if segment is None:
            return 0.0
        self._live_start = (segment.stream_id, segment.sequence)
        self._live_start_ready.set()
        parts = tuple(part.data for part in segment.parts)
        try:
            observed = await asyncio.to_thread(
                inspect_recording, segment.init, parts, False
            )
        except ValueError, OSError:
            self._check_attached()
            return 0.0
        self._check_attached()
        self.live_initial_burst = max(
            0.0,
            observed.observation_seconds
            - 2 * self._output.stream_settings.part_target_duration,
        )
        return self.live_initial_burst

    async def wait_live_start(self) -> None:
        """Wait for the live reader to select its initial segment."""
        await self._live_start_ready.wait()
        if self._closed:
            raise ValueError("Shared live stream is closed")

    def follow_live_start(self, other: SharedCameraStream) -> bool:
        """Start a second lease on the same shared output and pinned segment."""
        self._check_attached()
        if other._output is not self._output or other._live_start is None:
            return False
        self._live_start = other._live_start
        self.live_initial_burst = other.live_initial_burst
        return True

    async def live_parts(self) -> AsyncIterator[bytes]:
        """Yield initialization and low-latency parts, beginning at a keyframe."""
        stream_id: int | None = None
        sequence: int | None = None
        part_index = 0
        pinned = self._live_start
        while not self._closed:
            self._check_attached()
            self._output.idle_timer.awake()
            segments = tuple(self._output.get_segments())
            if stream_id is None and pinned is not None:
                stream_id, sequence = pinned
                current = next(
                    (s for s in segments if (s.stream_id, s.sequence) == pinned),
                    None,
                )
                if current is None:
                    if self._live_start == pinned:
                        self._live_start = None
                        self._live_start_ready.clear()
                    raise ValueError("Pinned live segment is no longer available")
                yield current.init
            if stream_id is None:
                for segment in reversed(segments):
                    if segment.parts and segment.parts[0].has_keyframe:
                        stream_id, sequence = segment.stream_id, segment.sequence
                        self._live_start = (stream_id, sequence)
                        self._live_start_ready.set()
                        yield segment.init
                        break
            if stream_id is not None:
                assert sequence is not None
                if segments and segments[-1].stream_id != stream_id:
                    if (
                        self._live_start is not None
                        and self._live_start[0] == stream_id
                    ):
                        self._live_start = None
                        self._live_start_ready.clear()
                    raise ValueError("Camera stream generation changed")
                current = next(
                    (
                        s
                        for s in segments
                        if s.sequence == sequence and s.stream_id == stream_id
                    ),
                    None,
                )
                if current is None:
                    raise ValueError("Live consumer missed stream segments")
                while part_index < len(current.parts):
                    part = current.parts[part_index]
                    if len(part.data) > _MAX_SNAPSHOT_BYTES:
                        raise ValueError("Live fragment exceeds byte limit")
                    part_index += 1
                    yield part.data
                # The consumer may have spent time sending each yielded part. A
                # segment may have arrived and signalled while it was suspended.
                segments = tuple(self._output.get_segments())
                if segments and segments[-1].stream_id != stream_id:
                    if (
                        self._live_start is not None
                        and self._live_start[0] == stream_id
                    ):
                        self._live_start = None
                        self._live_start_ready.clear()
                    raise ValueError("Camera stream generation changed")
                if not any(
                    s.sequence == sequence and s.stream_id == stream_id
                    for s in segments
                ):
                    raise ValueError("Live consumer missed stream segments")
                if current.complete and any(
                    s.sequence == sequence + 1 for s in segments
                ):
                    sequence += 1
                    part_index = 0
                    continue
            try:
                async with asyncio.timeout(1):
                    await self._output.part_recv()
            except TimeoutError:
                pass

    async def close(self) -> None:
        """Detach only this provider, preserving other shared stream outputs."""
        if self._close_task is None:
            self._closed = True
            self._live_start_ready.set()
            self._close_task = asyncio.create_task(self._finish_close())
        await asyncio.shield(self._close_task)

    async def _finish_close(self) -> None:
        """Finish release even when the caller awaiting close is cancelled."""
        if self._shared_entry is not None:
            entry = self._shared_entry
            async with entry.lock:
                entry.references -= 1
                if entry.references == 0 and entry.owner is not None:
                    await entry.owner.close()
                    entry.owner = None
                entry.discard_if_unused()
            return
        if self._attached():
            restore_clock = (
                self._output.requires_wallclock_timestamps is True
                and self._stream.pyav_options.get("use_wallclock_as_timestamps") != "1"
                and self._stream.is_running
            )
            await self._stream.remove_provider(self._output)
            if (
                restore_clock
                and self._stream.outputs()
                and not any(
                    getattr(output, "requires_wallclock_timestamps", False) is True
                    for output in self._stream.outputs().values()
                )
            ):
                self._stream.update_source(self._stream.source)


@dataclass(frozen=True, slots=True)
class MediaObservation:
    """Measured media properties; these do not guarantee future behavior."""

    video_codec: str
    h264_profile_idc: int
    h264_level_idc: int
    width: int
    height: int
    audio_codec: str | None
    audio_profile: str | None
    audio_rate: int | None
    audio_channels: int | None
    fps: float
    max_keyframe_interval: float
    peak_fps: int
    peak_video_bitrate: int
    average_video_bitrate: float
    observation_seconds: float
    audio_peak_bitrate: int = 0
    audio_object_type: int = 0
    audio_max_packet_bits: int = 0
    audio_continuous: bool = False
    h264_compatibility: int = 0


def _has_h264_idr(data: bytes, length_size: int) -> bool:
    """Check AVCC length-prefixed NAL units for an IDR slice."""
    if not 1 <= length_size <= 4:
        return False
    offset = 0
    while offset + length_size <= len(data):
        size = int.from_bytes(data[offset : offset + length_size], "big")
        offset += length_size
        if not size or offset + size > len(data):
            return False
        if data[offset] & 0x1F == 5:
            return True
        offset += size
    return False


class InsufficientMediaError(ValueError):
    """The media window is too short to measure keyframe cadence."""


def inspect_recording(
    initialization: bytes, fragments: tuple[bytes, ...], require_two_idrs: bool = True
) -> MediaObservation:
    """Inspect a bounded fMP4 sample using PyAV; call from an executor.

    Results only describe the supplied data and must not be used as a guarantee
    of future bitrate, keyframe cadence, timestamp continuity or codec stability.
    """
    from io import BytesIO  # noqa: PLC0415

    import av  # noqa: PLC0415

    size = len(initialization) + sum(map(len, fragments))
    if not fragments or size > _MAX_SNAPSHOT_BYTES:
        raise ValueError("Empty or oversized media sample")
    with av.open(
        BytesIO(initialization + b"".join(fragments)), format="mp4"
    ) as raw_container:
        container = cast("InputContainer", raw_container)
        videos = container.streams.video
        audios = container.streams.audio
        if len(videos) != 1 or len(audios) > 1:
            raise ValueError("Expected one video and at most one audio track")
        video = videos[0]
        codec = video.codec_context
        extra = codec.extradata or b""
        is_h264 = codec.name == "h264" and len(extra) >= 4 and extra[0] == 1
        if not codec.width or not codec.height:
            raise ValueError("Video dimensions unavailable")
        audio = audios[0].codec_context if audios else None
        audio_extra = audio.extradata or b"" if audio else b""
        audio_object_type = audio_extra[0] >> 3 if audio_extra else 0
        first = last = previous = None
        last_end = 0.0
        keyframes: list[float] = []
        video_bytes = 0
        video_packets = 0
        window: deque[tuple[float, int]] = deque()
        window_bytes = peak_bytes = peak_frames = 0
        audio_window: deque[tuple[float, int]] = deque()
        audio_window_bytes = audio_peak_bytes = audio_max_packet_bytes = 0
        audio_first = audio_last = None
        audio_valid = True
        streams = (video, audios[0]) if audios else (video,)
        for packet in container.demux(*streams):
            if packet.dts is None or packet.time_base is None:
                continue
            timestamp = float(packet.dts * packet.time_base)
            if audios and packet.stream.index == audios[0].index:
                if audio_last is not None and (
                    timestamp <= audio_last or timestamp - audio_last > 0.2
                ):
                    audio_valid = False
                if audio_first is None:
                    audio_first = timestamp
                audio_last = timestamp
                audio_window.append((timestamp, packet.size))
                audio_window_bytes += packet.size
                audio_max_packet_bytes = max(audio_max_packet_bytes, packet.size)
                while audio_window and audio_window[0][0] <= timestamp - 1 + 1e-6:
                    audio_window_bytes -= audio_window.popleft()[1]
                audio_peak_bytes = max(audio_peak_bytes, audio_window_bytes)
                continue
            if previous is not None and timestamp <= previous:
                raise ValueError("Nonmonotonic video timestamps")
            previous = last = timestamp
            last_end = timestamp + max(
                0, float((packet.duration or 0) * packet.time_base)
            )
            if first is None:
                first = timestamp
                if is_h264 and (
                    not packet.is_keyframe
                    or not _has_h264_idr(
                        bytes(packet), (extra[4] & 3) + 1 if len(extra) > 4 else 0
                    )
                ):
                    raise ValueError("H.264 fragment does not start with an IDR")
            if packet.is_keyframe:
                if is_h264 and not _has_h264_idr(
                    bytes(packet), (extra[4] & 3) + 1 if len(extra) > 4 else 0
                ):
                    raise ValueError("H.264 keyframe is not an IDR")
                keyframes.append(timestamp)
            video_bytes += packet.size
            video_packets += 1
            window.append((timestamp, packet.size))
            window_bytes += packet.size
            while window and window[0][0] <= timestamp - 1 + 1e-6:
                window_bytes -= window.popleft()[1]
            peak_bytes = max(peak_bytes, window_bytes)
            peak_frames = max(peak_frames, len(window))
        if (
            first is None
            or last is None
            or last <= first
            or len(keyframes) < (2 if require_two_idrs else 1)
        ):
            raise InsufficientMediaError(
                "Insufficient media to measure keyframe interval"
            )
        duration = last - first
        return MediaObservation(
            codec.name,
            extra[1] if is_h264 else 0,
            extra[3] if is_h264 else 0,
            codec.width,
            codec.height,
            audio.name if audio else None,
            audio.profile if audio else None,
            audio.sample_rate if audio else None,
            audio.channels if audio else None,
            (video_packets - 1) / duration,
            max(
                keyframes[0] - first,
                last_end - keyframes[-1],
                *(b - a for a, b in pairwise(keyframes)),
            ),
            peak_frames,
            peak_bytes * 8,
            video_bytes * 8 / duration,
            duration,
            audio_peak_bytes * 8,
            audio_object_type,
            audio_max_packet_bytes * 8,
            bool(
                audio_valid
                and audio_first is not None
                and audio_last is not None
                and audio_last - audio_first >= duration - 0.25
            ),
            extra[2] if is_h264 else 0,
        )

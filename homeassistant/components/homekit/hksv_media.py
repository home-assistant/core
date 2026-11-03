"""Bounded fragmented MP4 framing and prebuffer for HomeKit recordings."""

import asyncio
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
import logging
import struct
import time
from typing import TYPE_CHECKING

from homeassistant.components.stream.core import Orientation  # pylint: disable=home-assistant-component-root-import

if TYPE_CHECKING:
    from .hksv_config import RecordingConfiguration
    from .hksv_hardware import HardwareEncoder
    from .hksv_stream import MediaObservation, SharedFragment

_LOGGER = logging.getLogger(__name__)

MAX_BOX_SIZE = 16 * 1024 * 1024


async def read_box(
    reader: asyncio.StreamReader, max_size: int = MAX_BOX_SIZE
) -> tuple[bytes, bytes]:
    """Read one finite ISO BMFF box, rejecting malformed or oversized boxes."""
    first = await reader.read(1)
    if not first:
        raise EOFError
    header = first + await reader.readexactly(7)
    size, kind = struct.unpack(">I4s", header)
    if size == 1:
        extended = await reader.readexactly(8)
        header += extended
        size = struct.unpack(">Q", extended)[0]
    if size == 0 or size < len(header) or size > max_size:
        raise ValueError("Invalid or oversized MP4 box")
    return kind, header + await reader.readexactly(size - len(header))


@dataclass(frozen=True, slots=True)
class Fragment:
    """One complete movie fragment and its arrival time."""

    timestamp: float
    data: bytes


class FragmentBuffer:
    """Retain whole fragments within a hard byte and time budget."""

    def __init__(self, seconds: float, max_bytes: int) -> None:
        """Set time and byte limits."""
        if seconds <= 0 or max_bytes <= 0:
            raise ValueError("Buffer limits must be positive")
        self.seconds = seconds
        self.max_bytes = max_bytes
        self._fragments: deque[Fragment] = deque()
        self._size = 0
        self.initialization = b""

    def set_initialization(self, data: bytes) -> None:
        """Replace initialization data and discard incompatible fragments."""
        if len(data) > self.max_bytes:
            raise ValueError("Initialization segment exceeds buffer limit")
        self.initialization = data
        self._fragments.clear()
        self._size = len(data)

    def append(self, data: bytes, timestamp: float | None = None) -> None:
        """Store a complete fragment, evicting oldest data first."""
        now = time.monotonic() if timestamp is None else timestamp
        if self._fragments and now < self._fragments[-1].timestamp:
            raise ValueError("Fragment timestamps must be monotonic")
        if len(data) + len(self.initialization) > self.max_bytes:
            raise ValueError("Fragment exceeds buffer limit")
        self._fragments.append(Fragment(now, data))
        self._size += len(data)
        while self._fragments and (
            self._size > self.max_bytes
            or now - self._fragments[0].timestamp > self.seconds
        ):
            self._size -= len(self._fragments.popleft().data)

    def snapshot(
        self, timestamp: float | None = None
    ) -> tuple[bytes, tuple[bytes, ...]]:
        """Return immutable initialized fragment data still inside the time window."""
        now = time.monotonic() if timestamp is None else timestamp
        return self.initialization, tuple(
            f.data for f in self._fragments if now - f.timestamp <= self.seconds
        )


async def read_fragments(
    reader: asyncio.StreamReader,
    buffer: FragmentBuffer,
    on_fragment: Callable[[bytes], None] | None = None,
    on_initialization: Callable[[], None] | None = None,
) -> None:
    """Consume ftyp/moov initialization and complete moof/mdat fragment pairs."""
    init: list[bytes] = []
    moof: bytes | None = None
    initialized = False
    while True:
        try:
            kind, box = await read_box(reader)
        except EOFError:
            if initialized and moof is None:
                return
            raise ValueError("Truncated MP4 stream") from None
        if initialized and kind == b"mfra" and moof is None:
            return
        if not initialized:
            if kind not in (b"ftyp", b"moov", b"free") or (
                not init and kind != b"ftyp"
            ):
                raise ValueError("Expected MP4 initialization boxes")
            init.append(box)
            if sum(map(len, init)) > buffer.max_bytes:
                raise ValueError("Initialization segment exceeds buffer limit")
            if kind == b"moov":
                if (
                    init[0][4:8] != b"ftyp"
                    or sum(item[4:8] == b"ftyp" for item in init) != 1
                ):
                    raise ValueError("Invalid MP4 initialization segment")
                buffer.set_initialization(b"".join(init))
                initialized = True
                if on_initialization is not None:
                    on_initialization()
        elif kind in (b"free", b"styp", b"sidx") and moof is None:
            continue
        elif kind == b"moof" and moof is None:
            moof = box
        elif kind == b"mdat" and moof is not None:
            fragment = moof + box
            buffer.append(fragment)
            if on_fragment is not None:
                on_fragment(fragment)
            moof = None
        else:
            raise ValueError("Expected moof/mdat fragment pair")


class RecordingProcess:
    """Own a continuous FFmpeg process for a single recording configuration."""

    def __init__(self, command: list[str], seconds: float, max_bytes: int) -> None:
        """Set the process command and buffer limits."""
        if max_bytes < 3:
            raise ValueError("Recording memory limit is too small")
        self.command = command
        self._queue_budget = max_bytes // 3
        self.buffer = FragmentBuffer(seconds, max_bytes // 3)
        self.process: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task[None] | None = None
        self._input_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stop_task: asyncio.Task[None] | None = None
        self._stderr_bytes = 0
        self._ready = asyncio.Event()
        self._subscribers: dict[asyncio.Queue[bytes | None], int] = {}

    async def start(self, input_data: AsyncIterator[bytes] | None = None) -> None:
        """Start FFmpeg and its isolated fragment reader."""
        if self.process is not None or self._stop_task is not None:
            raise RuntimeError("Recording process is already running or stopped")
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if input_data is not None else None,
            stderr=asyncio.subprocess.PIPE,
        )
        assert self.process.stdout is not None
        self._task = asyncio.create_task(self._read(self.process.stdout))
        assert self.process.stderr is not None
        self._stderr_task = asyncio.create_task(self._drain_stderr(self.process.stderr))
        if input_data is not None:
            assert self.process.stdin is not None
            self._input_task = asyncio.create_task(
                self._feed(self.process.stdin, input_data)
            )

    async def _drain_stderr(self, reader: asyncio.StreamReader) -> None:
        """Drain diagnostics without retaining source credentials."""
        while chunk := await reader.read(4096):
            self._stderr_bytes += len(chunk)

    async def _feed(
        self, writer: asyncio.StreamWriter, source: AsyncIterator[bytes]
    ) -> None:
        try:
            async for chunk in source:
                writer.write(chunk)
                await writer.drain()
        except BrokenPipeError, ConnectionResetError:
            pass
        finally:
            writer.close()
            if close := getattr(source, "aclose", None):
                await close()

    async def _read(self, reader: asyncio.StreamReader) -> None:
        try:
            await read_fragments(reader, self.buffer, self._publish, self._ready.set)
        finally:
            self._ready.set()
            for queue in self._subscribers:
                if queue.full():
                    removed = queue.get_nowait()
                    if removed is not None:
                        self._subscribers[queue] -= len(removed)
                queue.put_nowait(None)

    def _publish(self, fragment: bytes) -> None:
        for queue, pending_bytes in self._subscribers.items():
            if queue.full() or pending_bytes + len(fragment) > self._queue_budget:
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)
                self._subscribers[queue] = 0
            else:
                queue.put_nowait(fragment)
                self._subscribers[queue] += len(fragment)

    async def fragments(self) -> AsyncGenerator[bytes]:
        """Yield initialization, buffered data, then new fragments to one client."""
        task = self._task
        if task is None:
            raise RuntimeError("Recording process is not running")
        await self._ready.wait()
        if self._stop_task is not None or self._task is not task:
            return
        if not self.buffer.initialization:
            raise RuntimeError("FFmpeg did not produce an initialization segment")
        if self._subscribers:
            raise RuntimeError("Only one recording subscriber is supported")
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=8)
        self._subscribers[queue] = 0
        initialization, buffered = self.buffer.snapshot()
        try:
            yield initialization
            for fragment in buffered:
                if self._stop_task is not None or self._task is not task:
                    return
                yield fragment
            if self._stop_task is not None or self._task is not task or task.done():
                return
            while (queued_fragment := await queue.get()) is not None:
                if self._stop_task is not None or self._task is not task:
                    return
                self._subscribers[queue] -= len(queued_fragment)
                yield queued_fragment
        finally:
            self._subscribers.pop(queue, None)

    @property
    def running(self) -> bool:
        """Return whether both encoder and reader are running."""
        return (
            self.process is not None
            and self.process.returncode is None
            and self._task is not None
            and not self._task.done()
        )

    @property
    def returncode(self) -> int | None:
        """Return the encoder exit status when available."""
        return self.process.returncode if self.process is not None else None

    async def wait(self) -> None:
        """Wait until the fragment reader finishes or fails."""
        if self._task is None:
            raise RuntimeError("Recording process is not running")
        await asyncio.shield(self._task)
        if self.process is not None and (code := await self.process.wait()) != 0:
            _LOGGER.warning(
                "HKSV FFmpeg exited with code %s and %s diagnostic bytes",
                code,
                self._stderr_bytes,
            )

    async def stop(self) -> None:
        """Stop the reader and reap FFmpeg even if it has already exited."""
        if self._stop_task is None:
            self._stop_task = asyncio.create_task(self._stop())
        await asyncio.shield(self._stop_task)

    async def _stop(self) -> None:
        process, task, input_task, stderr_task = (
            self.process,
            self._task,
            self._input_task,
            self._stderr_task,
        )
        self.process = None
        self._task = None
        self._input_task = None
        self._stderr_task = None
        if input_task is not None:
            input_task.cancel()
            await asyncio.gather(input_task, return_exceptions=True)
        if process is not None and process.returncode is None:
            with suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                await process.wait()
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if stderr_task is not None:
            await asyncio.gather(stderr_task, return_exceptions=True)


def orientation_video_filter(orientation: Orientation) -> str:
    """Return the FFmpeg filters matching the camera orientation."""
    return {
        Orientation.MIRROR: "hflip",
        Orientation.ROTATE_180: "hflip,vflip",
        Orientation.FLIP: "vflip",
        Orientation.ROTATE_LEFT_AND_FLIP: "transpose=clock,hflip",
        Orientation.ROTATE_LEFT: "transpose=cclock",
        Orientation.ROTATE_RIGHT_AND_FLIP: "transpose=clock,vflip",
        Orientation.ROTATE_RIGHT: "transpose=clock",
    }.get(orientation, "")


def ffmpeg_command(
    executable: str,
    input_args: list[str],
    configuration: RecordingConfiguration,
    audio_enabled: bool,
    *,
    copy_video: bool = False,
    copy_audio: bool = False,
    hardware: HardwareEncoder | None = None,
    orientation: Orientation = Orientation.NO_TRANSFORM,
) -> list[str]:
    """Build a fragmented MP4 encoder using the controller's selection."""
    profiles = ("baseline", "main", "high")
    levels = ("3.1", "3.2", "4.0")
    sample_rates = (8000, 16000, 24000, 32000, 44100, 48000)
    if configuration.profile >= len(profiles) or configuration.level >= len(levels):
        raise ValueError("Unsupported H.264 profile or level")
    if (
        configuration.audio_samplerate >= len(sample_rates)
        or configuration.audio_codec != 0
    ):
        raise ValueError("Unsupported audio configuration")
    if copy_video and orientation != Orientation.NO_TRANSFORM:
        raise ValueError("Video copy cannot apply camera orientation")
    interval = configuration.iframe_ms / 1000
    command = [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        *(hardware.global_args if hardware is not None else ()),
        *(["-noautorotate"] if orientation != Orientation.NO_TRANSFORM else []),
        *input_args,
        "-map",
        "0:v:0",
    ]
    if copy_video:
        command += ["-c:v", "copy"]
    else:
        video_filter = (
            f"scale={configuration.width}:{configuration.height}:"
            "force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={configuration.width}:{configuration.height}:(ow-iw)/2:(oh-ih)/2"
        )
        if orientation != Orientation.NO_TRANSFORM:
            video_filter = f"{orientation_video_filter(orientation)},{video_filter}"
        if hardware is not None:
            video_filter += f",{hardware.video_filter}"
        command += ["-vf", video_filter, "-r", str(configuration.fps), "-c:v"]
        if hardware is None:
            command += [
                "libx264",
                "-preset",
                "veryfast",
                "-tune",
                "zerolatency",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                profiles[configuration.profile],
                "-level:v",
                levels[configuration.level],
            ]
        else:
            command += [hardware.codec, *hardware.output_args]
        command += [
            "-b:v",
            f"{configuration.video_bitrate}k",
            "-maxrate",
            f"{configuration.video_bitrate}k",
            "-bufsize",
            f"{configuration.video_bitrate * 2}k",
            "-force_key_frames",
            f"expr:gte(t,n_forced*{interval})",
        ]
    if audio_enabled:
        command += ["-map", "0:a:0?"]
        if copy_audio:
            command += ["-c:a", "copy"]
        else:
            command += [
                "-c:a",
                "aac",
                "-ac",
                str(configuration.audio_channels),
                "-ar",
                str(sample_rates[configuration.audio_samplerate]),
                "-b:a",
                f"{configuration.audio_bitrate}k",
            ]
    else:
        command.append("-an")
    command += [
        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",
        *(
            []
            if copy_video
            else ["-min_frag_duration", str(configuration.fragment_ms * 1000)]
        ),
        "-f",
        "mp4",
        "pipe:1",
    ]
    return command


async def shared_mp4_input(
    source: AsyncIterator[SharedFragment],
) -> AsyncIterator[bytes]:
    """Feed one continuous shared-stream generation to FFmpeg."""
    generation: int | None = None
    try:
        async for fragment in source:
            if generation is None:
                generation = fragment.stream_id
                yield fragment.initialization
            elif fragment.stream_id != generation:
                return
            yield fragment.data
    finally:
        if close := getattr(source, "aclose", None):
            await close()


def can_copy_video(
    observed: MediaObservation,
    configuration: RecordingConfiguration,
    *,
    preserve_source: bool = False,
) -> bool:
    """Check observed source limits against the controller's selection."""
    if preserve_source:
        return (
            observed.video_codec == "h264"
            and observed.h264_profile_idc in (66, 77, 100)
            and observed.width > 0
            and observed.height > 0
            and observed.max_keyframe_interval > 0
            and observed.observation_seconds >= 2
        )
    profiles = (66, 77, 100)
    levels = (31, 32, 40)
    if configuration.profile >= len(profiles) or configuration.level >= len(levels):
        return False
    try:
        source_profile = profiles.index(observed.h264_profile_idc)
    except ValueError:
        return False
    return (
        observed.video_codec == "h264"
        and source_profile <= configuration.profile
        and observed.h264_level_idc <= levels[configuration.level]
        and observed.width == configuration.width
        and observed.height == configuration.height
        and 0 < observed.peak_fps <= configuration.fps
        and 0 < observed.peak_video_bitrate <= configuration.video_bitrate * 1000
        and 0 < observed.max_keyframe_interval * 1000 <= configuration.iframe_ms
        and observed.observation_seconds >= 2
    )


def can_copy_audio(
    observed: MediaObservation, configuration: RecordingConfiguration
) -> bool:
    """Check the observed AAC track against selected recording parameters."""
    sample_rates = (8000, 16000, 24000, 32000, 44100, 48000)
    if configuration.audio_samplerate >= len(sample_rates):
        return False
    return (
        configuration.audio_codec == 0
        and configuration.audio_bitrate_mode == 0
        and observed.audio_codec == "aac"
        and observed.audio_object_type == 2
        and observed.audio_continuous
        and observed.audio_rate == sample_rates[configuration.audio_samplerate]
        and observed.audio_channels == configuration.audio_channels
        # A one-second window can contain one partial AAC access unit extra.
        and observed.audio_max_packet_bits > 0
        and 0
        < observed.audio_peak_bitrate
        <= configuration.audio_bitrate * 1000 + observed.audio_max_packet_bits
        and observed.observation_seconds >= 2
    )

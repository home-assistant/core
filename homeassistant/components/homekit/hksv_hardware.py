"""Bounded functional H.264 hardware encoder probing for HomeKit."""

import asyncio
from collections import OrderedDict
from contextlib import suppress
from dataclasses import dataclass
from glob import glob
import time
from typing import Final

_PROFILES: Final = (("baseline", 66), ("main", 77), ("high", 100))
_LEVELS: Final = (("3.1", 31), ("3.2", 32), ("4.0", 40))
_PROBE_TIMEOUT: Final = 5
_CACHE_SIZE: Final = 32


@dataclass(frozen=True, slots=True)
class HardwareEncoder:
    """FFmpeg arguments for a tested H.264 hardware path."""

    codec: str
    global_args: tuple[str, ...]
    video_filter: str
    output_args: tuple[str, ...]


def _candidates(profile: str, level: str) -> tuple[HardwareEncoder, ...]:
    """Build candidate paths without probing any camera."""
    args = ("-profile:v", profile, "-level:v", level)
    candidates = []
    if glob("/dev/nvidia[0-9]*"):
        candidates.append(HardwareEncoder("h264_nvenc", (), "format=nv12", args))
    for device in sorted(glob("/dev/dri/render" + "D*")):
        candidates.extend(
            (
                HardwareEncoder(
                    "h264_qsv",
                    ("-init_hw_device", f"qsv=hk:{device}", "-filter_hw_device", "hk"),
                    "format=nv12,hwupload=extra_hw_frames=16",
                    args,
                ),
                HardwareEncoder(
                    "h264_vaapi",
                    ("-vaapi_device", device),
                    "format=nv12,hwupload",
                    args,
                ),
            )
        )
    return tuple(candidates)


def _matches_sps(data: bytes, profile: int, level: int) -> bool:
    """Check the profile and upper level in an Annex B H.264 sequence header."""
    start = 0
    while (position := data.find(b"\x00\x00\x01", start)) >= 0:
        nal = position + 3
        if len(data) >= nal + 4 and data[nal] & 0x1F == 7:
            return (
                data[nal + 1] == profile
                and data[nal + 3] <= level
                and (profile != 66 or bool(data[nal + 2] & 0x40))
            )
        start = nal
    return False


class HardwareEncoderProbe:
    """Share bounded, profile-specific hardware tests among cameras."""

    def __init__(self) -> None:
        """Initialize a per-instance bounded LRU cache."""
        self._cache: OrderedDict[
            tuple[str, int, int, int, int, int], tuple[HardwareEncoder | None, float]
        ] = OrderedDict()
        self._lock = asyncio.Lock()
        self._disabled_until: dict[str, float] = {}
        self._generation = 0

    def invalidate(self) -> None:
        """Clear cached results after an operational failure or device change."""
        self._cache.clear()
        self._generation += 1

    def report_failure(self, codec: str) -> None:
        """Temporarily avoid a device that failed during normal operation."""
        if codec not in {"h264_nvenc", "h264_qsv", "h264_vaapi"}:
            return
        self._disabled_until[codec] = time.monotonic() + 300
        self.invalidate()

    async def select(
        self, ffmpeg: str, profile: int, level: int, width: int, height: int, fps: int
    ) -> HardwareEncoder | None:
        """Select a working encoder, or None for software fallback.

        Only a synthetic source is used. A test does not guarantee that a
        device remains available or can encode the requested number of streams.
        """
        if (
            profile not in range(len(_PROFILES))
            or level not in range(len(_LEVELS))
            or not 16 <= width <= 4096
            or not 16 <= height <= 4096
            or width % 2
            or height % 2
            or not 1 <= fps <= 60
        ):
            return None
        key = (ffmpeg, profile, level, width, height, fps)
        async with self._lock:
            if key in self._cache:
                cached, expires = self._cache[key]
                if cached is not None or time.monotonic() < expires:
                    self._cache.move_to_end(key)
                    return cached
                del self._cache[key]
            profile_name, profile_idc = _PROFILES[profile]
            level_name, level_idc = _LEVELS[level]
            result = None
            generation = self._generation
            skipped = False
            candidates = await asyncio.to_thread(_candidates, profile_name, level_name)
            for candidate in candidates:
                if self._disabled_until.get(candidate.codec, 0) > time.monotonic():
                    skipped = True
                    continue
                if await self._test(
                    ffmpeg, candidate, width, height, fps, profile_idc, level_idc
                ):
                    result = candidate
                    break
            if generation != self._generation:
                return None
            if result is None and skipped:
                return None
            self._cache[key] = (result, time.monotonic() + 300)
            if len(self._cache) > _CACHE_SIZE:
                self._cache.popitem(last=False)
            return result

    async def _test(
        self,
        ffmpeg: str,
        candidate: HardwareEncoder,
        width: int,
        height: int,
        fps: int,
        profile: int,
        level: int,
    ) -> bool:
        """Encode a few synthetic frames and verify the emitted SPS."""
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                *candidate.global_args,
                "-f",
                "lavfi",
                "-i",
                f"color=size={width}x{height}:rate={fps}",
                "-frames:v",
                "3",
                "-an",
                "-vf",
                candidate.video_filter,
                "-c:v",
                candidate.codec,
                *candidate.output_args,
                "-f",
                "h264",
                "pipe:1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                stdin=asyncio.subprocess.DEVNULL,
            )
            async with asyncio.timeout(_PROBE_TIMEOUT):
                data, _ = await proc.communicate()
            return proc.returncode == 0 and _matches_sps(data, profile, level)
        except OSError, TimeoutError:
            return False
        finally:
            if proc is not None and proc.returncode is None:
                with suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()


HARDWARE_ENCODER_PROBE = HardwareEncoderProbe()

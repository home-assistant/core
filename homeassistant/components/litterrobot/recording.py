"""Event-triggered WebRTC video recording for Litter-Robot cameras."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fractions import Fraction
import logging
from pathlib import Path
import queue
import subprocess
import threading
from typing import Any

from pylitterbot import LitterRobot5

from homeassistant.core import HomeAssistant

from .const import DEFAULT_RECORDING_DURATION, DEFAULT_RECORDING_RETENTION_DAYS

_LOGGER = logging.getLogger(__name__)
COOLDOWN_SECONDS = 60
FRAME_QUEUE_MAXSIZE = 100
WEBRTC_CONNECT_TIMEOUT = 30
RECORDING_FPS = 15

# Visit recording constants
VIEW_SWITCH_DELAY = 15  # seconds on front camera before switching to globe
POST_VISIT_GRACE = 10  # seconds to keep recording after PET_VISIT
MAX_VISIT_DURATION = 600  # 10 min safety timeout

# Cycle recording constants
POST_CYCLE_GRACE = 5  # seconds to keep recording after cycle ends
MAX_CYCLE_DURATION = 300  # 5 min safety timeout


@dataclass
class VisitContext:
    """State for a continuous visit recording session."""

    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    pet_name: str = "unknown"
    pet_id: str | None = None


@dataclass
class CycleContext:
    """State for a continuous cycle recording session."""

    stop_event: asyncio.Event = field(default_factory=asyncio.Event)


class RecordingManager:
    """Manage event-triggered video recording sessions."""

    def __init__(
        self,
        hass: HomeAssistant,
        media_dir: Path,
        duration: int = DEFAULT_RECORDING_DURATION,
        retention_days: int = DEFAULT_RECORDING_RETENTION_DAYS,
    ) -> None:
        """Initialize the recording manager."""
        self._hass = hass
        self._media_dir = media_dir
        self._duration = duration
        self._retention_days = retention_days
        self._active_recordings: dict[str, asyncio.Task[None]] = {}
        self._last_trigger_times: dict[tuple[str, str], datetime] = {}
        self._visit_contexts: dict[str, VisitContext] = {}
        self._cycle_contexts: dict[str, CycleContext] = {}

    def trigger_recording(
        self,
        robot: LitterRobot5,
        activity: dict[str, Any],
        pet_name_map: dict[str, str] | None = None,
        camera_view: str | None = None,
    ) -> None:
        """Start a fixed-duration recording if cooldown and concurrency checks pass."""
        serial = robot.serial
        now = datetime.now()

        event_type = str(
            activity.get("eventType", activity.get("type", "event"))
        ).lower()

        # Resolve pet identity for PET_VISIT events
        pet_id: str | None = None
        pet_name = "unknown"
        if "pet_visit" in event_type or "petvisit" in event_type:
            raw = activity.get("petId") or (
                activity.get("petIds") or [None]
            )[0]
            if raw:
                pet_id = str(raw)
                if pet_name_map:
                    pet_name = pet_name_map.get(pet_id, "unknown")

        # Per-event cooldown key: (serial, pet_id) for pet visits,
        # (serial, event_type) for everything else
        cooldown_key: tuple[str, str] = (
            (serial, pet_id) if pet_id else (serial, event_type)
        )

        last_trigger = self._last_trigger_times.get(cooldown_key)
        if last_trigger and (now - last_trigger).total_seconds() < COOLDOWN_SECONDS:
            _LOGGER.debug(
                "Skipping recording for %s: cooldown active (%s)",
                robot.name,
                cooldown_key[1],
            )
            return

        # Per-robot concurrency check (one recording at a time per robot)
        if serial in self._active_recordings:
            task = self._active_recordings[serial]
            if not task.done():
                _LOGGER.debug(
                    "Skipping recording for %s: already recording", robot.name
                )
                return
            del self._active_recordings[serial]

        self._last_trigger_times[cooldown_key] = now

        # Build filename with pet name for PET_VISIT, event type for others
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        if pet_id:
            filename = f"{timestamp}_PET_VISIT_{pet_name}.mp4"
        else:
            filename = f"{timestamp}_{event_type.upper()}.mp4"

        robot_dir = self._media_dir / serial
        robot_dir.mkdir(parents=True, exist_ok=True)

        task = self._hass.async_create_background_task(
            self._record(robot, robot_dir / filename, camera_view=camera_view),
            name=f"litterrobot_recording_{serial}",
        )
        self._active_recordings[serial] = task

    def trigger_visit_recording(self, robot: LitterRobot5) -> None:
        """Start a continuous visit recording (front → globe camera switch).

        Triggered by cat_detect events. Records until PET_VISIT signals
        completion or MAX_VISIT_DURATION timeout is reached.
        """
        serial = robot.serial
        now = datetime.now()

        # Per-robot concurrency check
        if serial in self._active_recordings:
            task = self._active_recordings[serial]
            if not task.done():
                _LOGGER.debug(
                    "Skipping visit recording for %s: already recording",
                    robot.name,
                )
                return
            del self._active_recordings[serial]

        # Cooldown for cat_detect
        cooldown_key: tuple[str, str] = (serial, "cat_detect")
        last_trigger = self._last_trigger_times.get(cooldown_key)
        if last_trigger and (now - last_trigger).total_seconds() < COOLDOWN_SECONDS:
            _LOGGER.debug(
                "Skipping visit recording for %s: cooldown active", robot.name
            )
            return

        self._last_trigger_times[cooldown_key] = now

        visit_ctx = VisitContext()
        self._visit_contexts[serial] = visit_ctx

        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_VISIT.mp4"

        robot_dir = self._media_dir / serial
        robot_dir.mkdir(parents=True, exist_ok=True)
        filepath = robot_dir / filename

        task = self._hass.async_create_background_task(
            self._record_visit(robot, filepath, visit_ctx),
            name=f"litterrobot_visit_{serial}",
        )
        self._active_recordings[serial] = task

    def signal_visit_complete(
        self, serial: str, pet_name: str = "unknown", pet_id: str | None = None
    ) -> bool:
        """Signal that a visit recording should stop (called on PET_VISIT).

        Returns True if an active visit was signaled, False otherwise.
        """
        visit_ctx = self._visit_contexts.get(serial)
        if visit_ctx is None:
            return False

        visit_ctx.pet_name = pet_name
        visit_ctx.pet_id = pet_id
        visit_ctx.stop_event.set()
        _LOGGER.debug(
            "Visit complete signaled for %s: pet=%s", serial, pet_name
        )
        return True

    def trigger_cycle_recording(self, robot: LitterRobot5) -> None:
        """Start a continuous cycle recording on globe camera.

        Records until signal_cycle_complete is called (state leaves CLEAN_CYCLE)
        or MAX_CYCLE_DURATION timeout is reached.
        """
        serial = robot.serial
        now = datetime.now()

        # Per-robot concurrency check
        if serial in self._active_recordings:
            task = self._active_recordings[serial]
            if not task.done():
                _LOGGER.debug(
                    "Skipping cycle recording for %s: already recording",
                    robot.name,
                )
                return
            del self._active_recordings[serial]

        cycle_ctx = CycleContext()
        self._cycle_contexts[serial] = cycle_ctx

        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_CYCLE.mp4"

        robot_dir = self._media_dir / serial
        robot_dir.mkdir(parents=True, exist_ok=True)
        filepath = robot_dir / filename

        task = self._hass.async_create_background_task(
            self._record_cycle(robot, filepath, cycle_ctx),
            name=f"litterrobot_cycle_{serial}",
        )
        self._active_recordings[serial] = task

    def signal_cycle_complete(self, serial: str) -> bool:
        """Signal that a cycle recording should stop.

        Returns True if an active cycle was signaled, False otherwise.
        """
        cycle_ctx = self._cycle_contexts.get(serial)
        if cycle_ctx is None:
            return False

        cycle_ctx.stop_event.set()
        _LOGGER.debug("Cycle complete signaled for %s", serial)
        return True

    async def _record_cycle(
        self,
        robot: LitterRobot5,
        filepath: Path,
        cycle_ctx: CycleContext,
    ) -> None:
        """Record a full clean cycle on globe camera.

        Records until the cycle completes (signaled by coordinator) or
        MAX_CYCLE_DURATION timeout.
        """
        serial = robot.serial
        tmp_path = filepath.with_name(f".{filepath.name}.tmp")

        _LOGGER.info(
            "Starting cycle recording for %s: %s", robot.name, filepath.name
        )

        try:
            await robot.set_camera_view("globe")
            _LOGGER.debug("Set camera view to globe for %s", robot.name)
        except Exception:
            _LOGGER.warning(
                "Failed to set camera view to globe for %s",
                robot.name,
                exc_info=True,
            )

        frame_queue: queue.Queue[Any] = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
        encoder_stop = threading.Event()
        encoder_error: list[Exception] = []

        def on_video_frame(frame: Any) -> None:
            """Put frames into the queue, dropping if full."""
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass

        encoder_thread = threading.Thread(
            target=self._encode_mp4,
            args=(frame_queue, encoder_stop, tmp_path, encoder_error),
            name=f"lr_encoder_{serial}",
            daemon=True,
        )
        encoder_thread.start()

        stream = None
        try:
            stream = robot.create_camera_stream()
            stream.on_video_frame(on_video_frame)
            await stream.start()

            connected = await stream.wait_for_connection(
                timeout=WEBRTC_CONNECT_TIMEOUT
            )
            if not connected:
                _LOGGER.warning(
                    "WebRTC connection timeout for %s, aborting cycle recording",
                    robot.name,
                )
                return

            _LOGGER.debug(
                "WebRTC connected for %s, cycle recording active", robot.name
            )

            # Wait for cycle complete signal or max timeout
            try:
                await asyncio.wait_for(
                    cycle_ctx.stop_event.wait(),
                    timeout=MAX_CYCLE_DURATION,
                )
                _LOGGER.debug(
                    "Cycle complete for %s, grace period %ds",
                    robot.name,
                    POST_CYCLE_GRACE,
                )
            except TimeoutError:
                _LOGGER.warning(
                    "Cycle recording timeout for %s after %ds",
                    robot.name,
                    MAX_CYCLE_DURATION,
                )

            # Brief grace period after cycle ends
            await asyncio.sleep(POST_CYCLE_GRACE)

        except Exception:
            _LOGGER.warning(
                "Cycle recording failed for %s", robot.name, exc_info=True
            )
        finally:
            encoder_stop.set()

            if stream is not None:
                try:
                    await stream.stop()
                except Exception:
                    _LOGGER.debug(
                        "Error stopping camera stream for %s",
                        robot.name,
                        exc_info=True,
                    )

            await self._hass.async_add_executor_job(encoder_thread.join, 10.0)

            self._cycle_contexts.pop(serial, None)

            if serial in self._active_recordings:
                del self._active_recordings[serial]

        await self._finalize_recording(robot.name, tmp_path, filepath, encoder_error)

    async def _record(
        self,
        robot: LitterRobot5,
        filepath: Path,
        camera_view: str | None = None,
    ) -> None:
        """Record fixed-duration video from the camera via server-side WebRTC."""
        serial = robot.serial
        tmp_path = filepath.with_name(f".{filepath.name}.tmp")

        _LOGGER.info("Starting recording for %s: %s", robot.name, filepath.name)

        if camera_view is not None:
            try:
                await robot.set_camera_view(camera_view)
                _LOGGER.debug("Set camera view to %s for %s", camera_view, robot.name)
            except Exception:
                _LOGGER.warning(
                    "Failed to set camera view to %s for %s",
                    camera_view,
                    robot.name,
                    exc_info=True,
                )

        frame_queue: queue.Queue[Any] = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
        stop_event = threading.Event()
        encoder_error: list[Exception] = []

        def on_video_frame(frame: Any) -> None:
            """Put frames into the queue, dropping if full."""
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass

        encoder_thread = threading.Thread(
            target=self._encode_mp4,
            args=(frame_queue, stop_event, tmp_path, encoder_error),
            name=f"lr_encoder_{serial}",
            daemon=True,
        )
        encoder_thread.start()

        stream = None
        try:
            stream = robot.create_camera_stream()
            stream.on_video_frame(on_video_frame)
            await stream.start()

            connected = await stream.wait_for_connection(
                timeout=WEBRTC_CONNECT_TIMEOUT
            )
            if not connected:
                _LOGGER.warning(
                    "WebRTC connection timeout for %s, aborting recording",
                    robot.name,
                )
                return

            _LOGGER.debug(
                "WebRTC connected for %s, recording for %ds",
                robot.name,
                self._duration,
            )
            await asyncio.sleep(self._duration)

        except Exception:
            _LOGGER.warning(
                "Recording failed for %s", robot.name, exc_info=True
            )
        finally:
            stop_event.set()

            if stream is not None:
                try:
                    await stream.stop()
                except Exception:
                    _LOGGER.debug(
                        "Error stopping camera stream for %s",
                        robot.name,
                        exc_info=True,
                    )

            await self._hass.async_add_executor_job(encoder_thread.join, 10.0)

            if serial in self._active_recordings:
                del self._active_recordings[serial]

        await self._finalize_recording(robot.name, tmp_path, filepath, encoder_error)

    async def _record_visit(
        self,
        robot: LitterRobot5,
        filepath: Path,
        visit_ctx: VisitContext,
    ) -> None:
        """Record a continuous visit (front camera → globe camera switch).

        Starts on the front camera, switches to globe after VIEW_SWITCH_DELAY,
        and records until PET_VISIT signals or MAX_VISIT_DURATION timeout.
        """
        serial = robot.serial
        tmp_path = filepath.with_name(f".{filepath.name}.tmp")

        _LOGGER.info(
            "Starting visit recording for %s: %s", robot.name, filepath.name
        )

        # Start on front camera to capture approach
        try:
            await robot.set_camera_view("front")
            _LOGGER.debug("Set camera view to front for %s", robot.name)
        except Exception:
            _LOGGER.warning(
                "Failed to set camera view to front for %s",
                robot.name,
                exc_info=True,
            )

        frame_queue: queue.Queue[Any] = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
        encoder_stop = threading.Event()
        encoder_error: list[Exception] = []

        def on_video_frame(frame: Any) -> None:
            """Put frames into the queue, dropping if full."""
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass

        encoder_thread = threading.Thread(
            target=self._encode_mp4,
            args=(frame_queue, encoder_stop, tmp_path, encoder_error),
            name=f"lr_encoder_{serial}",
            daemon=True,
        )
        encoder_thread.start()

        stream = None
        switch_task: asyncio.Task[None] | None = None
        try:
            stream = robot.create_camera_stream()
            stream.on_video_frame(on_video_frame)
            await stream.start()

            connected = await stream.wait_for_connection(
                timeout=WEBRTC_CONNECT_TIMEOUT
            )
            if not connected:
                _LOGGER.warning(
                    "WebRTC connection timeout for %s, aborting visit recording",
                    robot.name,
                )
                return

            _LOGGER.debug("WebRTC connected for %s, visit recording active", robot.name)

            # Schedule camera switch from front to globe
            async def _switch_to_globe() -> None:
                await asyncio.sleep(VIEW_SWITCH_DELAY)
                try:
                    await robot.set_camera_view("globe")
                    _LOGGER.debug(
                        "Switched camera to globe for %s", robot.name
                    )
                except Exception:
                    _LOGGER.warning(
                        "Failed to switch camera to globe for %s",
                        robot.name,
                        exc_info=True,
                    )

            switch_task = asyncio.create_task(_switch_to_globe())

            # Wait for visit complete signal or max timeout
            try:
                await asyncio.wait_for(
                    visit_ctx.stop_event.wait(),
                    timeout=MAX_VISIT_DURATION,
                )
                _LOGGER.debug(
                    "Visit complete for %s, pet=%s, grace period %ds",
                    robot.name,
                    visit_ctx.pet_name,
                    POST_VISIT_GRACE,
                )
            except TimeoutError:
                _LOGGER.warning(
                    "Visit recording timeout for %s after %ds",
                    robot.name,
                    MAX_VISIT_DURATION,
                )

            if switch_task is not None and not switch_task.done():
                switch_task.cancel()

            # Grace period to capture cat leaving
            await asyncio.sleep(POST_VISIT_GRACE)

        except Exception:
            _LOGGER.warning(
                "Visit recording failed for %s", robot.name, exc_info=True
            )
        finally:
            if switch_task is not None and not switch_task.done():
                switch_task.cancel()

            encoder_stop.set()

            if stream is not None:
                try:
                    await stream.stop()
                except Exception:
                    _LOGGER.debug(
                        "Error stopping camera stream for %s",
                        robot.name,
                        exc_info=True,
                    )

            await self._hass.async_add_executor_job(encoder_thread.join, 10.0)

            # Clean up visit context
            self._visit_contexts.pop(serial, None)

            if serial in self._active_recordings:
                del self._active_recordings[serial]

        # Rename file with pet name if visit was completed with pet info
        final_filepath = filepath
        if visit_ctx.pet_name != "unknown":
            new_name = filepath.name.replace("_VISIT.", f"_VISIT_{visit_ctx.pet_name}.")
            final_filepath = filepath.with_name(new_name)

        await self._finalize_recording(robot.name, tmp_path, final_filepath, encoder_error)

    async def _finalize_recording(
        self,
        robot_name: str,
        tmp_path: Path,
        filepath: Path,
        encoder_error: list[Exception],
    ) -> None:
        """Check encoder results and apply faststart post-processing."""
        if encoder_error:
            _LOGGER.warning(
                "Encoding failed for %s: %s", robot_name, encoder_error[0]
            )
            if tmp_path.exists():
                tmp_path.unlink()
            return

        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            try:
                await self._hass.async_add_executor_job(
                    self._apply_faststart, tmp_path, filepath
                )
            except Exception:
                _LOGGER.warning(
                    "faststart post-processing failed for %s, saving as-is",
                    robot_name,
                    exc_info=True,
                )
                tmp_path.rename(filepath)
            _LOGGER.info("Recording saved: %s", filepath.name)
        elif tmp_path.exists():
            tmp_path.unlink()
            _LOGGER.warning(
                "Recording empty for %s, removed temp file", robot_name
            )

    @staticmethod
    def _encode_mp4(
        frame_queue: queue.Queue[Any],
        stop_event: threading.Event,
        filepath: Path,
        errors: list[Exception],
    ) -> None:
        """Encode video frames to H.264 MP4 (runs in encoder thread)."""
        try:
            import av  # noqa: PLC0415
        except ImportError:
            errors.append(ImportError("PyAV (av) is required for recording"))
            return

        container = None
        stream = None
        frame_count = 0

        try:
            container = av.open(str(filepath), mode="w", format="mp4")
            stream = container.add_stream("libx264", rate=RECORDING_FPS)
            stream.options = {"preset": "ultrafast", "crf": "23"}
            stream.pix_fmt = "yuv420p"

            while not stop_event.is_set() or not frame_queue.empty():
                try:
                    frame = frame_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if stream.width == 0:
                    stream.width = frame.width
                    stream.height = frame.height

                yuv_frame = frame.reformat(
                    width=stream.width,
                    height=stream.height,
                    format="yuv420p",
                )
                yuv_frame.pts = frame_count
                yuv_frame.time_base = Fraction(1, RECORDING_FPS)

                for packet in stream.encode(yuv_frame):
                    container.mux(packet)
                frame_count += 1

            # Flush encoder
            if stream is not None:
                for packet in stream.encode():
                    container.mux(packet)

        except Exception as exc:
            errors.append(exc)
        finally:
            if container is not None:
                container.close()

        if frame_count == 0 and not errors:
            _LOGGER.debug("Encoder finished with 0 frames")

    @staticmethod
    def _apply_faststart(tmp_path: Path, filepath: Path) -> None:
        """Move the moov atom to the start of the MP4 for browser streaming.

        Runs ffmpeg as a stream copy (no re-encode) to produce a faststart MP4,
        then removes the temp file. Raises RuntimeError if ffmpeg fails.
        """
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(tmp_path),
                "-c",
                "copy",
                "-movflags",
                "faststart",
                str(filepath),
            ],
            capture_output=True,
        )
        tmp_path.unlink()
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg faststart failed: {result.stderr.decode(errors='replace')[:300]}"
            )

    async def async_cleanup_old_recordings(self) -> None:
        """Delete recordings older than the retention period."""
        cutoff = datetime.now() - timedelta(days=self._retention_days)
        removed = 0

        def _cleanup() -> int:
            count = 0
            if not self._media_dir.exists():
                return count
            for mp4 in self._media_dir.rglob("*.mp4"):
                if datetime.fromtimestamp(mp4.stat().st_mtime) < cutoff:
                    mp4.unlink()
                    count += 1
            # Remove empty robot directories
            for subdir in self._media_dir.iterdir():
                if subdir.is_dir() and not any(subdir.iterdir()):
                    subdir.rmdir()
            return count

        removed = await self._hass.async_add_executor_job(_cleanup)
        if removed:
            _LOGGER.info("Cleaned up %d old recording(s)", removed)

    async def async_stop(self) -> None:
        """Cancel all active recording tasks."""
        # Signal all active visit and cycle recordings to stop
        for visit_ctx in self._visit_contexts.values():
            visit_ctx.stop_event.set()
        self._visit_contexts.clear()

        for cycle_ctx in self._cycle_contexts.values():
            cycle_ctx.stop_event.set()
        self._cycle_contexts.clear()

        for serial, task in list(self._active_recordings.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            _LOGGER.debug("Cancelled recording for %s", serial)
        self._active_recordings.clear()

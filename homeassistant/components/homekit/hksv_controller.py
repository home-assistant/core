"""Experimental per-camera HomeKit Secure Video lifecycle.

The owner must explicitly attach services and stop this controller on teardown.
"""

import asyncio
import base64
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing, suppress
from dataclasses import replace
import logging
import time
from typing import Any, NoReturn

from pyhap.datastream import HDSReject, HDSServer
from pyhap.secure_video import HKSVServices, RecordingCapabilities, b64, parse_selected

from homeassistant.components.stream.core import Orientation  # pylint: disable=home-assistant-component-root-import
from homeassistant.exceptions import HomeAssistantError

from .hksv_config import RecordingConfiguration
from .hksv_hardware import HARDWARE_ENCODER_PROBE as _HARDWARE_PROBE, HardwareEncoder
from .hksv_media import (
    RecordingProcess,
    can_copy_audio,
    can_copy_video,
    ffmpeg_command,
    shared_mp4_input,
)
from .hksv_stream import (
    InsufficientMediaError,
    MediaObservation,
    SharedCameraStream,
    SharedFragment,
    inspect_recording,
)

_LOGGER = logging.getLogger(__name__)


class HKSVController:
    """Own one camera's HDS listener and independently bounded recording process."""

    def __init__(
        self,
        source: Callable[[], Awaitable[SharedCameraStream | None]],
        ffmpeg: str,
        store: Any,
        on_camera_disabled: Callable[[], None] | None = None,
        on_state_loaded: Callable[[], None] | None = None,
        on_stream_disabled: Callable[[int], None] | None = None,
        *,
        camera_entity_id: str = "camera",
        prebuffer_seconds: int = 4,
        quality: str = "compatible",
        preserve_source: bool = True,
        on_capabilities_changed: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize detached services and the recording lifecycle."""
        if prebuffer_seconds not in (4, 8):
            raise ValueError("Unsupported Secure Video prebuffer")
        if quality not in ("compatible", "high"):
            raise ValueError("Unsupported Secure Video quality")
        self.preserve_source = preserve_source
        self.on_capabilities_changed = on_capabilities_changed
        self.source = source
        self.camera_entity_id = camera_entity_id
        self.ffmpeg = ffmpeg
        self.store = store
        self.on_camera_disabled = on_camera_disabled
        self.on_state_loaded = on_state_loaded
        self.on_stream_disabled = on_stream_disabled
        self._stream_active_values: dict[int, bool] = {}
        self._ready = False
        self._privacy_ready = False
        self._selected_value: str | None = None
        self._native_resolution: tuple[int, int, int] | None = None
        self.capabilities = RecordingCapabilities(
            1280,
            720,
            15,
            0,
            2,
            0,
            2,
            prebuffer_ms=prebuffer_seconds * 1000,
            resolutions=(
                (1280, 720, 15),
                (1280, 720, 30),
                (1920, 1080, 15),
                (1920, 1080, 30),
            ),
            profiles=(2,) if quality == "high" else (0, 1, 2),
            levels=(2,),
        )
        self._persisted_profiles = list(self.capabilities.profiles)
        self.configuration: RecordingConfiguration | None = None
        self.hds = HDSServer(self._open_recording)
        self.services = HKSVServices(
            self.hds, self.capabilities, self._set_configuration
        )
        for char, handler in (
            (self.services.active, self._change_active),
            (self.services.camera_active, self._change_camera_active),
            (self.services.audio_active, self._change_audio_active),
            (self.services.event_snapshots, self._change_snapshots),
            (self.services.periodic_snapshots, self._change_snapshots),
        ):
            char.session_setter_callback = (
                lambda value, session, char=char, handler=handler: self._session_write(
                    char, handler, value
                )
            )
        selected_setter = self.services.selected.session_setter_callback
        self.services.selected.session_setter_callback = lambda value, session: (
            self._selected_write(selected_setter, value, session)
        )
        self.active = False
        self.camera_active = True
        self.audio_active = False
        self._process: RecordingProcess | None = None
        self._active_hardware: HardwareEncoder | None = None
        self._active_copy = (False, False)
        self._shared: Any = None
        self._process_key: tuple[RecordingConfiguration, bool, Orientation] | None = (
            None
        )
        self._reconcile_task: asyncio.Task | None = None
        self._monitor_task: asyncio.Task | None = None
        self._restart_attempts = 0
        self._video_copy_disabled = False
        self._audio_copy_disabled = False
        self._force_software = False
        self._lock = asyncio.Lock()
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        self._cleanup_tasks: set[asyncio.Task[None]] = set()
        self._stream_active = False
        self._recording_owner: object | None = None
        self._hds_accepted = 0
        self._hds_rejected = 0
        self._hds_final_offered = 0
        self._hds_interrupted = 0
        self._motion_until = 0.0
        self._motion_detected = False

    def _session_write(self, char: Any, handler: Callable, value: Any) -> None:
        if not self._ready or self._closed:
            raise RuntimeError("HKSV settings are still loading")
        handler(value)
        char.set_value(value)

    def _selected_write(self, handler: Callable, value: str, session: Any) -> None:
        if not self._ready or self._closed:
            raise RuntimeError("HKSV settings are still loading")
        handler(value, session)

    def _set_configuration(self, raw: bytes) -> None:
        selected = parse_selected(raw, self.capabilities)
        self.configuration = RecordingConfiguration.from_mapping(selected)
        self._video_copy_disabled = False
        self._audio_copy_disabled = False
        self._force_software = False
        self._restart_attempts = 0
        self._selected_value = b64(raw)
        self._schedule_save()
        self._schedule_reconcile()

    def _change_active(self, value: Any) -> None:
        if value not in (0, 1):
            raise ValueError("invalid recording active value")
        self.active = bool(value)
        self._restart_attempts = 0
        self._schedule_save()
        self._schedule_reconcile()

    def _change_camera_active(self, value: Any) -> None:
        if value not in (0, 1):
            raise ValueError("invalid camera active value")
        self.camera_active = bool(value)
        if not self.camera_active and self._recording_owner is not None:
            self.hds.close_owner(self._recording_owner)
        if self.on_state_loaded:
            self.on_state_loaded()
        if not self.camera_active and self.on_camera_disabled:
            self.on_camera_disabled()
        self._schedule_save()
        self._schedule_reconcile()

    def _change_audio_active(self, value: Any) -> None:
        if value not in (0, 1):
            raise ValueError("invalid audio active value")
        self.audio_active = bool(value)
        self._restart_attempts = 0
        self._schedule_save()
        self._schedule_reconcile()

    def _change_snapshots(self, value: Any) -> None:
        if value not in (0, 1):
            raise ValueError("invalid snapshots active value")
        # Characteristic is updated after callback; delay collecting the value.
        asyncio.get_running_loop().call_soon(self._schedule_save)

    def _state(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "camera_active": self.camera_active,
            "audio_active": self.audio_active,
            "selected": self._selected_value,
            "event_snapshots": self.services.event_snapshots.value,
            "periodic_snapshots": self.services.periodic_snapshots.value,
            "stream_active": self._stream_active_values,
            "native_resolution": self._native_resolution,
            "recording_profiles": self._persisted_profiles,
        }

    def _schedule_save(self) -> None:
        if self._ready and not self._closed:
            self.store.async_delay_save(self._state, 1)

    def stream_active(self, index: int) -> bool:
        """Return the persisted streaming permission for a stream slot."""
        return self._stream_active_values.get(index, True)

    def set_stream_active(self, index: int, value: int) -> None:
        """Store a HomeKit stream slot permission."""
        if not self._ready or index < 0 or value not in (0, 1):
            raise ValueError("Invalid stream active value")
        self._stream_active_values[index] = bool(value)
        if self.on_state_loaded:
            self.on_state_loaded()
        if not value and self.on_stream_disabled:
            self.on_stream_disabled(index)
        self._schedule_save()

    @property
    def ready(self) -> bool:
        """Return whether persisted settings and the listener are ready."""
        return self._ready

    @property
    def privacy_ready(self) -> bool:
        """Return whether persisted privacy state has been restored."""
        return self._privacy_ready

    def snapshot_allowed(self, reason: int | None) -> bool:
        """Apply HomeKit snapshot permissions; unknown reasons fail closed."""
        if not self._privacy_ready or not self.camera_active:
            return False
        event = bool(self.services.event_snapshots.value)
        periodic = bool(self.services.periodic_snapshots.value)
        if reason is None:
            return event and periodic
        if reason == 0:
            return periodic
        if reason == 1:
            return event
        return False

    def motion(self, detected: bool) -> None:
        """Keep the recording open briefly after the latest motion detection."""
        self._motion_detected = detected
        if detected:
            self._motion_until = time.monotonic() + 8

    def _is_closed(self) -> bool:
        return self._closed

    async def start(self) -> None:
        """Start the listener before accepting HDS setup."""
        if self._closed:
            return
        state = await self.store.async_load() or {}
        if self._is_closed():
            return
        old_profiles = state.get("recording_profiles", [0, 1, 2])
        profiles_changed = bool(state) and old_profiles != list(
            self.capabilities.profiles
        )
        if profiles_changed:
            self._persisted_profiles = old_profiles
        native_resolution = state.get("native_resolution")
        if (
            isinstance(native_resolution, list)
            and len(native_resolution) == 3
            and all(isinstance(item, int) for item in native_resolution)
        ):
            self._set_native_resolution(tuple(native_resolution))
        if selected := state.get("selected"):
            try:
                raw = base64.b64decode(selected, validate=True)
                self._set_configuration(raw)
                self.services.selected.set_value(selected, should_notify=False)
            except ValueError, TypeError:
                _LOGGER.warning("Ignoring invalid stored HKSV configuration")
        for key, char in (
            ("active", self.services.active),
            ("camera_active", self.services.camera_active),
            ("audio_active", self.services.audio_active),
            ("event_snapshots", self.services.event_snapshots),
            ("periodic_snapshots", self.services.periodic_snapshots),
        ):
            if key in state and state[key] in (0, 1, False, True):
                char.set_value(int(state[key]), should_notify=False)
        self.active = bool(self.services.active.value)
        self.camera_active = bool(self.services.camera_active.value)
        self.audio_active = bool(self.services.audio_active.value)
        for key, value in state.get("stream_active", {}).items():
            if str(key).isdigit() and value in (0, 1, False, True):
                self._stream_active_values[int(key)] = bool(value)
        if self.on_state_loaded:
            self.on_state_loaded()
        self._privacy_ready = True
        if self.camera_active and self._native_resolution is None:
            await self._discover_native()
        await self.hds.start()
        if self._is_closed():
            await self.hds.close()
            return
        self._ready = True
        self._schedule_reconcile()
        if profiles_changed and self.on_capabilities_changed:
            try:
                await self.on_capabilities_changed()
            except Exception:
                _LOGGER.exception("Could not publish changed HKSV capabilities")
            else:
                self._persisted_profiles = list(self.capabilities.profiles)
        try:
            await self.store.async_save(self._state())
        except Exception:
            _LOGGER.exception("Could not persist HKSV capabilities")

    def _set_native_resolution(self, resolution: tuple[int, int, int]) -> None:
        """Add one bounded observed resolution alongside required fallback formats."""
        width, height, fps = resolution
        if not (0 < width <= 1920 and 0 < height <= 1080 and fps in (15, 30)):
            return
        self._native_resolution = resolution
        resolutions = tuple(dict.fromkeys((*self.capabilities.resolutions, resolution)))
        self.capabilities = replace(self.capabilities, resolutions=resolutions)
        _, video, _ = self.capabilities.supported()
        self.services.recording.get_characteristic(
            "Supported Video Recording Configuration"
        ).set_value(video)

    async def _discover_native(self) -> None:
        """Probe a shared source without changing its existing HLS provider."""
        shared = None
        try:
            async with asyncio.timeout(12):
                shared = await self.source()
                if shared is None:
                    return
                while not self._closed:
                    fragments = shared.snapshot()
                    if len(fragments) >= 2:
                        observed = await asyncio.to_thread(
                            inspect_recording,
                            fragments[-2].initialization,
                            (fragments[-2].data, fragments[-1].data),
                        )
                        if (
                            observed.h264_profile_idc in (66, 77, 100)
                            and observed.h264_level_idc <= 40
                            and 0 < observed.peak_fps <= 30
                        ):
                            self._set_native_resolution(
                                (
                                    observed.width,
                                    observed.height,
                                    15 if observed.peak_fps <= 15 else 30,
                                )
                            )
                        return
                    await asyncio.sleep(0.5)
        except TimeoutError, ValueError, OSError, HomeAssistantError:
            _LOGGER.debug("Could not probe native HKSV video format")
        finally:
            if shared:
                await shared.close()

    def _schedule_reconcile(self) -> None:
        if not self._ready or self._closed:
            return
        if self._reconcile_task is None or self._reconcile_task.done():
            self._reconcile_task = asyncio.create_task(self._reconcile())

    def source_orientation_changed(self) -> None:
        """Reconcile recording when the shared camera orientation changes."""
        self._schedule_reconcile()

    async def _cleanup(
        self, process: RecordingProcess | None, shared: SharedCameraStream | None
    ) -> None:
        """Retain cleanup ownership even when its caller is cancelled."""

        async def cleanup() -> None:
            try:
                if process:
                    await process.stop()
            finally:
                if shared:
                    await shared.close()

        task = asyncio.create_task(cleanup())
        self._cleanup_tasks.add(task)

        def finished(done: asyncio.Task[None]) -> None:
            self._cleanup_tasks.discard(done)
            if not done.cancelled() and (error := done.exception()):
                _LOGGER.error("HKSV resource cleanup failed", exc_info=error)

        task.add_done_callback(finished)
        await asyncio.shield(task)

    async def _reconcile(self) -> None:
        async with self._lock:
            while not self._closed:
                config = self.configuration
                desired = (
                    (config, self.audio_active)
                    if self.active and self.camera_active and config
                    else None
                )
                if desired is None:
                    if self._process is None and self._shared is None:
                        return
                elif (
                    self._process is not None
                    and self._shared is not None
                    and (*desired, self._shared.orientation) == self._process_key
                ):
                    return
                previous, self._process = self._process, None
                old_shared, self._shared = self._shared, None
                self._process_key = None
                if previous or old_shared:
                    await self._cleanup(previous, old_shared)
                    continue
                if desired is None:
                    return
                shared = None
                process = None
                try:
                    shared = await self.source()
                    if shared is None:
                        raise RuntimeError("camera has no shared stream")  # noqa: TRY301
                    copy_video, copy_audio = await self._probe_copy(
                        shared, desired[0], desired[1]
                    )
                    orientation = shared.orientation
                    if orientation != Orientation.NO_TRANSFORM:
                        copy_video = False
                    hardware = None
                    if not copy_video and not self._force_software:
                        hardware = await _HARDWARE_PROBE.select(
                            self.ffmpeg,
                            desired[0].profile,
                            desired[0].level,
                            desired[0].width,
                            desired[0].height,
                            desired[0].fps,
                        )
                    command = ffmpeg_command(
                        self.ffmpeg,
                        ["-i", "pipe:0"],
                        desired[0],
                        desired[1],
                        copy_video=copy_video,
                        copy_audio=copy_audio,
                        hardware=hardware,
                        orientation=orientation,
                    )
                    process = RecordingProcess(
                        command, desired[0].prebuffer_ms / 1000, 32 * 1024 * 1024
                    )
                    source = (
                        self._monitored_copy(shared, desired[0], copy_video, copy_audio)
                        if copy_video or copy_audio
                        else shared.fragments()
                    )
                    await process.start(shared_mp4_input(source))
                except asyncio.CancelledError:
                    await self._cleanup(process, shared)
                    raise
                except Exception:
                    await self._cleanup(process, shared)
                    _LOGGER.exception("Could not start HKSV recording buffer")
                    if self._restart_attempts >= 3:
                        _LOGGER.error(
                            "HKSV recording buffer stopped after repeated FFmpeg failures"
                        )
                        return
                    self._restart_attempts += 1
                    await asyncio.sleep(2 ** (self._restart_attempts - 1))
                    if not self.active or not self.camera_active:
                        return
                    continue
                # State may have changed while acquiring source or launching FFmpeg.
                if (
                    self._closed
                    or not self.active
                    or not self.camera_active
                    or self.configuration != desired[0]
                    or self.audio_active != desired[1]
                    or shared.orientation != orientation
                ):
                    await self._cleanup(process, shared)
                    continue
                self._process, self._process_key = process, (*desired, orientation)
                self._active_hardware = hardware
                self._active_copy = (copy_video, copy_audio)
                self._shared = shared
                _LOGGER.info(
                    "%s: Secure Video encoder video=%s audio=%s selected=%sx%s %sfps",
                    self.camera_entity_id,
                    "copy" if copy_video else hardware.codec if hardware else "libx264",
                    "copy" if copy_audio else "aac" if desired[1] else "off",
                    desired[0].width,
                    desired[0].height,
                    desired[0].fps,
                )
                self._monitor_task = asyncio.create_task(self._monitor(process))
                return

    async def _inspect_native_window(
        self, fragments: tuple[SharedFragment, ...]
    ) -> MediaObservation | None:
        """Prefer the current segment, then a bounded contiguous window."""
        if not fragments:
            return None
        observed = None
        with suppress(InsufficientMediaError):
            observed = await asyncio.to_thread(
                inspect_recording,
                fragments[-1].initialization,
                (fragments[-1].data,),
                False,
            )
        if observed is not None and observed.observation_seconds >= 2:
            return observed
        window: list[SharedFragment] = []
        size = 0
        for fragment in reversed(fragments[-8:]):
            if window and (
                fragment.stream_id != window[0].stream_id
                or fragment.sequence + 1 != window[0].sequence
                or fragment.initialization != window[0].initialization
            ):
                break
            size += len(fragment.data)
            if size + len(fragment.initialization) > 32 * 1024 * 1024:
                break
            window.insert(0, fragment)
        if len(window) < 2:
            return observed
        try:
            return await asyncio.to_thread(
                inspect_recording,
                window[0].initialization,
                tuple(fragment.data for fragment in window),
                False,
            )
        except InsufficientMediaError:
            return observed

    async def observe_live_source(
        self, shared: SharedCameraStream | None = None
    ) -> MediaObservation | None:
        """Inspect current shared media without opening another camera connection."""
        supplied = shared is not None
        shared = shared or self._shared
        if shared is None or shared.orientation != Orientation.NO_TRANSFORM:
            return None
        try:
            fragments = (
                shared.snapshot(include_partial=True)
                if self.preserve_source
                else shared.snapshot()
            )
            if not fragments:
                return None
            if self.preserve_source:
                observed = await self._inspect_native_window(fragments)
            else:
                selected = fragments[-2:]
                if len(selected) < 2:
                    return None
                observed = await asyncio.to_thread(
                    inspect_recording,
                    selected[0].initialization,
                    tuple(fragment.data for fragment in selected),
                    True,
                )
        except Exception:  # noqa: BLE001 - optional inspection must not block live video
            _LOGGER.debug("Could not inspect shared source for live video")
            return None
        else:
            if shared.orientation != Orientation.NO_TRANSFORM:
                return None
            if supplied:
                try:
                    shared._check_attached()  # noqa: SLF001
                    if shared._closed:  # noqa: SLF001
                        return None
                except ValueError:
                    return None
                return observed
            return observed if shared is self._shared else None

    async def _probe_copy(
        self,
        shared: SharedCameraStream,
        config: RecordingConfiguration,
        audio_enabled: bool,
    ) -> tuple[bool, bool]:
        """Select each track independently after observing a compatible window."""
        deadline = time.monotonic() + (20 if self.preserve_source else 10)
        while not self._closed and time.monotonic() < deadline:
            fragments = (
                shared.snapshot(include_partial=True)
                if self.preserve_source
                else shared.snapshot()
            )
            window = fragments[-1:]
            if not self.preserve_source:
                contiguous: list[SharedFragment] = []
                for fragment in reversed(fragments[-8:]):
                    if contiguous and (
                        fragment.stream_id != contiguous[0].stream_id
                        or fragment.sequence + 1 != contiguous[0].sequence
                        or fragment.initialization != contiguous[0].initialization
                    ):
                        break
                    contiguous.insert(0, fragment)
                window = tuple(contiguous)
            if window and (self.preserve_source or len(window) >= 2):
                try:
                    if self.preserve_source:
                        observed = await self._inspect_native_window(fragments)
                    else:
                        observed = await asyncio.to_thread(
                            inspect_recording,
                            window[0].initialization,
                            tuple(fragment.data for fragment in window),
                            True,
                        )
                except InsufficientMediaError:
                    pass
                except ValueError:
                    if not self.preserve_source:
                        return False, False
                except OSError:
                    if not self.preserve_source:
                        return False, False
                else:
                    if observed is not None and observed.observation_seconds >= 2:
                        copy_video = not self._video_copy_disabled and can_copy_video(
                            observed, config, preserve_source=self.preserve_source
                        )
                        copy_audio = False
                        if (
                            audio_enabled
                            and not self._audio_copy_disabled
                            and len(fragments) >= 2
                            and fragments[-2].stream_id == fragments[-1].stream_id
                            and fragments[-2].sequence + 1 == fragments[-1].sequence
                            and fragments[-2].initialization
                            == fragments[-1].initialization
                        ):
                            try:
                                audio_observed = await asyncio.to_thread(
                                    inspect_recording,
                                    fragments[-2].initialization,
                                    (fragments[-2].data, fragments[-1].data),
                                    not self.preserve_source,
                                )
                            except ValueError, OSError:
                                pass
                            else:
                                copy_audio = can_copy_audio(audio_observed, config)
                        return copy_video, copy_audio
            await asyncio.sleep(0.5)
        return False, False

    async def _monitored_copy(
        self,
        shared: SharedCameraStream,
        config: RecordingConfiguration,
        copy_video: bool,
        copy_audio: bool,
    ) -> AsyncIterator[SharedFragment]:
        """Validate each overlapping window before releasing copied media."""
        window: list[SharedFragment] = []
        pending: list[SharedFragment] = []
        async for fragment in shared.fragments():
            if window and (
                fragment.stream_id != window[-1].stream_id
                or fragment.sequence != window[-1].sequence + 1
                or fragment.initialization != window[-1].initialization
            ):
                return
            window.append(fragment)
            window = window[-(2 if self.preserve_source else 8) :]
            pending.append(fragment)
            if (
                sum(len(item.data) for item in pending) > 32 * 1024 * 1024
                or sum(len(item.data) for item in window) > 32 * 1024 * 1024
            ):
                self._video_copy_disabled |= copy_video
                self._audio_copy_disabled |= copy_audio
                return
            if not self.preserve_source and len(window) < 2:
                continue
            windows: list[tuple[bytes, ...]] = (
                [(fragment.data,)] if self.preserve_source else []
            )
            if len(window) >= 2:
                windows.append(tuple(item.data for item in window))
            insufficient = False
            for index, data in enumerate(windows):
                try:
                    observed = await asyncio.to_thread(
                        inspect_recording,
                        fragment.initialization,
                        data,
                        not self.preserve_source,
                    )
                except InsufficientMediaError:
                    if index + 1 < len(windows):
                        continue
                    insufficient = True
                    break
                except ValueError:
                    self._video_copy_disabled |= copy_video
                    self._audio_copy_disabled |= copy_audio
                    return
                except OSError:
                    self._video_copy_disabled |= copy_video
                    self._audio_copy_disabled |= copy_audio
                    return
                if observed.observation_seconds < 2:
                    if index + 1 < len(windows):
                        continue
                    insufficient = True
                    break
                video_failed = copy_video and not can_copy_video(
                    observed, config, preserve_source=self.preserve_source
                )
                audio_failed = copy_audio and not can_copy_audio(observed, config)
                if video_failed or audio_failed:
                    self._video_copy_disabled |= video_failed
                    self._audio_copy_disabled |= audio_failed
                    return
            if insufficient:
                if len(pending) == 8:
                    self._video_copy_disabled |= copy_video
                    self._audio_copy_disabled |= copy_audio
                    return
                continue
            for buffered in pending:
                yield buffered
            pending.clear()

    async def _monitor(self, process: RecordingProcess) -> None:
        """Restart unexpectedly terminated encoders at most three times."""
        started = time.monotonic()
        failed = False
        try:
            await process.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            failed = True
            _LOGGER.exception("HKSV fragment reader failed")
        if self._closed or self._process is not process:
            return
        hardware, self._active_hardware = self._active_hardware, None
        copy_video, copy_audio = self._active_copy
        self._active_copy = (False, False)
        process_failed = failed or process.returncode not in (None, 0)
        retry_without_audio_copy = (
            process_failed
            and copy_audio
            and not (copy_video and self._video_copy_disabled)
        )
        if retry_without_audio_copy:
            self._audio_copy_disabled = True
        elif process_failed and copy_video:
            self._video_copy_disabled = True
        if hardware is not None and process_failed and not retry_without_audio_copy:
            _HARDWARE_PROBE.report_failure(hardware.codec)
            self._force_software = True
            self._restart_attempts = 0
            _LOGGER.warning("HKSV hardware encoder failed; switching to software")
        self._process = None
        self._process_key = None
        shared, self._shared = self._shared, None
        await self._cleanup(process, shared)
        if time.monotonic() - started >= 60:
            self._restart_attempts = 0
        if self._restart_attempts >= 3:
            _LOGGER.error(
                "HKSV recording buffer stopped after repeated FFmpeg failures"
            )
            return
        self._restart_attempts += 1
        await asyncio.sleep(2 ** (self._restart_attempts - 1))
        if not self._closed:
            self._schedule_reconcile()

    def _reject_recording(self, reason: int, category: str) -> NoReturn:
        self._hds_rejected += 1
        _LOGGER.info(
            "%s: Secure Video recording request rejected category=%s total_rejected=%s",
            self.camera_entity_id,
            category,
            self._hds_rejected,
        )
        raise HDSReject(reason)

    def _open_recording(
        self, owner: object, stream_id: int
    ) -> AsyncIterator[tuple[bytes, bool]]:
        if not self._ready or not self.active or not self.camera_active:
            self._reject_recording(1, "inactive")
        if self.configuration is None:
            self._reject_recording(9, "configuration")
        if self._stream_active:
            self._reject_recording(2, "busy")
        process = self._process
        if process is None or not process.running:
            self._reject_recording(5, "buffer_unavailable")
        self._hds_accepted += 1
        _LOGGER.info(
            "%s: Secure Video recording request accepted by delegate total_accepted=%s",
            self.camera_entity_id,
            self._hds_accepted,
        )
        return self._recording(process, owner)

    def _can_deliver_recording(self) -> bool:
        """Check privacy before sending recording data."""
        return not self._closed and self.camera_active

    async def _recording(
        self, process: RecordingProcess, owner: object | None = None
    ) -> AsyncIterator[tuple[bytes, bool]]:
        if self._stream_active:
            self._reject_recording(2, "busy")
        if not self._can_deliver_recording():
            return
        self._stream_active = True
        self._recording_owner = owner
        completed = False
        media_fragments = 0
        try:
            start = time.monotonic()
            first = True
            async with aclosing(process.fragments()) as fragments:
                async for fragment in fragments:
                    if not self._can_deliver_recording():
                        return
                    if first:
                        first = False
                        yield fragment, False
                        if not self._can_deliver_recording():
                            return
                        continue
                    media_fragments += 1
                    # A HomeKit request is itself an event; allow a full fragment even
                    # if motion was only a short event pulse. Cap individual clips.
                    last = (
                        not self.active
                        or (
                            not self._motion_detected
                            and time.monotonic() >= self._motion_until
                            and time.monotonic() - start >= 4
                        )
                        or time.monotonic() - start >= 60
                    )
                    if last:
                        completed = True
                        self._hds_final_offered += 1
                        _LOGGER.info(
                            "%s: Secure Video final fragment offered to transport fragments=%s total_final_offered=%s; delivery and acknowledgement not observed by delegate",
                            self.camera_entity_id,
                            media_fragments,
                            self._hds_final_offered,
                        )
                    yield fragment, last
                    if last or not self._can_deliver_recording():
                        return
        finally:
            self._recording_owner = None
            self._stream_active = False
            if not completed:
                self._hds_interrupted += 1
                _LOGGER.info(
                    "%s: Secure Video recording producer interrupted fragments=%s total_interrupted=%s",
                    self.camera_entity_id,
                    media_fragments,
                    self._hds_interrupted,
                )

    async def close(self) -> None:
        """Stop sessions and join cleanup even if the caller is cancelled."""
        self._closed = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await asyncio.shield(self._close_task)

    async def _close(self) -> None:
        """Own the shutdown independently of individual callers."""
        if self._ready:
            try:
                await self.store.async_save(self._state())
            except Exception:
                _LOGGER.exception("Could not persist HKSV state during shutdown")
        await self.hds.close()
        if self._monitor_task:
            self._monitor_task.cancel()
            await asyncio.gather(self._monitor_task, return_exceptions=True)
        if self._reconcile_task:
            self._reconcile_task.cancel()
            await asyncio.gather(self._reconcile_task, return_exceptions=True)
        async with self._lock:
            process, self._process = self._process, None
            shared, self._shared = self._shared, None
            if process or shared:
                await self._cleanup(process, shared)
            self._process_key = None
        if self._cleanup_tasks:
            await asyncio.gather(*self._cleanup_tasks, return_exceptions=True)

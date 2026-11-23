"""Data update coordinator for builtin reCamera Pro YOLO results."""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
import json
import logging
import time
from typing import Any, override
from urllib.parse import quote, urlsplit, urlunsplit

import aiohttp
from recamera_protocol import (
    DetectedClass,
    RecameraAuthenticationError,
    RecameraConnectionError,
    RecameraDeviceClient,
    RecameraDeviceInfo,
    RecameraError,
    RecameraProtocolError,
    RecameraValidationError,
    ResultObservation,
    SourceStatusRecord,
    async_probe_device,
    format_url_host,
    normalize_source_status,
    parse_result_hub_message,
    stable_class_token,
)

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .capture_controller import CaptureController
from .const import (
    AUDIO_SOURCE_ID,
    CONF_AUDIO_CONFIDENCE,
    CONF_AUDIO_COOLDOWN,
    CONF_CLASS_STALE_SECONDS,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_CANDIDATES,
    CONF_LANGUAGE,
    CONF_SW_VERSION,
    CONF_TRACKED_CLASSES,
    CONF_VISUAL_CONFIDENCE,
    CONF_VISUAL_CONFIRM,
    CONF_VISUAL_COOLDOWN,
    DEFAULT_AUDIO_CONFIDENCE,
    DEFAULT_AUDIO_COOLDOWN,
    DEFAULT_CLASS_STALE_SECONDS,
    DEFAULT_TRACKED_CLASSES,
    DEFAULT_VISUAL_CONFIDENCE,
    DEFAULT_VISUAL_CONFIRM,
    DEFAULT_VISUAL_COOLDOWN,
    DIRECT_RESULTS_SUBSCRIBE,
    DIRECT_RESULTS_WS_PATH,
    DOMAIN,
    EVENT_FIRMWARE_UPDATE_COMPLETED,
    EVENT_HISTORY_LIMIT,
    FIRMWARE_REBOOT_TIMEOUT_SECONDS,
    FIRMWARE_RECONNECT_POLL_SECONDS,
    MOTION_APP_ID,
    MOTION_TRANSITION_TIMEOUT_SECONDS,
    OTA_CHECK_INTERVAL_SECONDS,
    OTA_DOWNLOAD_TIMEOUT_SECONDS,
    OTA_POLL_INTERVAL_SECONDS,
    OTA_RELEASE_LATEST_API_URL,
    OTA_RELEASE_URL,
    SOURCE_AVAILABLE,
    SOURCE_OFFLINE_SECONDS,
    SOURCE_UNAVAILABLE,
    SOURCE_UNKNOWN,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
    WEBSOCKET_RETRY_MAX,
    WEBSOCKET_RETRY_MIN,
)
from .discovery_candidates import (
    drop_discovery_candidate,
    merge_discovery_candidate,
    recoverable_discovery_candidates,
    valid_discovery_candidates,
)
from .event_context import new_event_context
from .identity import probe_identity_mismatch
from .source_state import (
    DetectionState,
    EventRecord,
    expire_detection_state,
    update_source_health,
    update_source_observations,
)


def _raise_firmware_download_timeout() -> None:
    """Raise a typed connection error when OTA download exceeds deadline."""
    raise RecameraConnectionError("firmware_download_timeout")


def _raise_firmware_download_failed() -> None:
    """Raise a typed protocol error when OTA download reports failure."""
    raise RecameraProtocolError("firmware_download_failed")


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MotionDetectionState:
    """Observed motion-detect App and result state."""

    installed: bool = False
    running: bool = False
    system_app: bool = False
    system_source_confirmed: bool = False
    motion: bool | None = None
    score: float | None = None
    changed_ratio: float | None = None
    changed_pixels: int | None = None
    last_seen: datetime | None = None
    reason: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    app_health: str = SOURCE_UNKNOWN
    error: str | None = None
    last_confirmed: datetime | None = None
    config_health: str = SOURCE_UNKNOWN
    config_error: str | None = None
    config_last_confirmed: datetime | None = None
    event_id: str | None = None
    sequence: int | None = None
    transitioning: bool = False
    target_running: bool | None = None
    transition_started_at: datetime | None = None
    transition_error: str | None = None


@dataclass(slots=True)
class RecameraRuntimeData:
    """State shared with camera, event, binary sensor, and sensor platforms."""

    info: RecameraDeviceInfo
    capabilities: dict[str, Any]
    stream_info: dict[str, Any]
    media_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    media_errors: dict[str, str] = field(default_factory=dict)
    class_catalog: dict[str, DetectedClass] = field(default_factory=dict)
    visual: DetectionState = field(default_factory=DetectionState)
    audio: DetectionState = field(default_factory=DetectionState)
    motion: MotionDetectionState = field(default_factory=MotionDetectionState)
    websocket_connected: bool = False
    stream_ready: bool = False
    last_stream_message: datetime | None = None


@dataclass(frozen=True, slots=True)
class FirmwareUpdateState:
    """Last known firmware update state."""

    installed_version: str | None = None
    latest_version: str | None = None
    published_version: str | None = None
    target_version: str | None = None
    available: bool = False
    confirm_token: str | None = None
    in_progress: bool = False
    update_percentage: int | None = None
    status: str = "idle"
    operation: str | None = None
    last_checked: datetime | None = None


def _normalized_firmware_version(value: object) -> str:
    """Normalize vendor firmware version prefixes for comparison."""
    return str(value or "").strip().lstrip("vV")


def _firmware_started_at(value: object) -> datetime | None:
    """Return a trustworthy UTC reboot start time."""
    try:
        started_at = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    if started_at.tzinfo is None:
        return None
    now = datetime.now(UTC)
    if started_at > now + timedelta(seconds=30):
        return None
    return min(started_at, now)


class RecameraCoordinator(DataUpdateCoordinator[RecameraRuntimeData]):
    """Coordinate device metadata, media metadata, and builtin YOLO."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}.{config_entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self.config_entry = config_entry
        use_hass_session = hasattr(hass, "loop") and hasattr(
            RecameraDeviceClient, "async_set_rtsp_stream_enabled"
        )
        self._client_session: aiohttp.ClientSession | None = (
            async_create_clientsession(
                hass,
                verify_ssl=False,
                auto_cleanup=True,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
            if use_hass_session
            else None
        )
        self.client = RecameraDeviceClient(
            str(config_entry.data[CONF_HOST]),
            str(config_entry.data[CONF_USERNAME]),
            str(config_entry.data[CONF_PASSWORD]),
            session=self._client_session,
        )
        self.device_id = str(
            config_entry.data.get(CONF_DEVICE_ID)
            or config_entry.unique_id
            or config_entry.entry_id
        )
        self.capture_controller = CaptureController(
            hass,
            self.client,
            device_id=self.device_id,
            entry_id=config_entry.entry_id,
        )
        self.tracked_class_keys = frozenset(
            str(item)
            for item in config_entry.options.get(
                CONF_TRACKED_CLASSES, DEFAULT_TRACKED_CLASSES
            )
        )
        self.visual_min_confidence = self._option_float(
            CONF_VISUAL_CONFIDENCE,
            DEFAULT_VISUAL_CONFIDENCE,
            minimum=0.0,
            maximum=1.0,
        )
        self.visual_confirm_seconds = self._option_float(
            CONF_VISUAL_CONFIRM,
            DEFAULT_VISUAL_CONFIRM,
            minimum=0.0,
            maximum=30.0,
        )
        self.audio_min_confidence = self._option_float(
            CONF_AUDIO_CONFIDENCE,
            DEFAULT_AUDIO_CONFIDENCE,
            minimum=0.0,
            maximum=1.0,
        )
        self.class_stale_seconds = self._option_float(
            CONF_CLASS_STALE_SECONDS,
            DEFAULT_CLASS_STALE_SECONDS,
            minimum=1.0,
            maximum=60.0,
        )
        self.visual_cooldown = self._option_float(
            CONF_VISUAL_COOLDOWN,
            DEFAULT_VISUAL_COOLDOWN,
            minimum=0.0,
            maximum=60.0,
        )
        self.audio_cooldown = self._option_float(
            CONF_AUDIO_COOLDOWN,
            DEFAULT_AUDIO_COOLDOWN,
            minimum=0.0,
            maximum=60.0,
        )
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{config_entry.entry_id}",
        )
        self._websocket_task: asyncio.Task[None] | None = None
        self._connection_recovery_task: asyncio.Task[None] | None = None
        self._stale_task: asyncio.Task[None] | None = None
        self._video_update_lock = asyncio.Lock()
        self._motion_lock = asyncio.Lock()
        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        self._stop = asyncio.Event()
        self._activity_event = asyncio.Event()
        self.connection_generation = 0
        self._reauth_started = False
        self._unsub_stop: Callable[[], None] | None = None
        self._event_sequence = 0
        self._last_summary_publish: dict[str, float] = {}
        self._firmware_update = FirmwareUpdateState(
            installed_version=self.client.info.firmware_version
        )
        self._firmware_lock = asyncio.Lock()
        self._firmware_reboot: dict[str, Any] | None = None
        self._firmware_check_task: asyncio.Task[None] | None = None
        self._firmware_reboot_task: asyncio.Task[None] | None = None
        self._motion_seen_events: deque[tuple[object, ...]] = deque(maxlen=256)
        self._motion_generation = 0
        self._cached_stream_info: dict[str, dict[str, Any]] = {}
        self._stream_stop_callbacks: dict[str, list[Callable[[], Any]]] = {}

    def _option_float(
        self,
        key: str,
        default: float,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        """Read a bounded float option."""
        try:
            value = float(self.config_entry.options.get(key, default))
        except TypeError, ValueError:
            return default
        return min(maximum, max(minimum, value))

    @property
    def stream_ready(self) -> bool:
        """Return whether at least one Result Hub envelope was received."""
        return bool(self.data and self.data.stream_ready)

    def source_state(self, source_id: str) -> DetectionState | None:
        """Return visual or sound state for the requested source."""
        if self.data is None:
            return None
        if source_id == "builtin":
            return self.data.visual
        if source_id == AUDIO_SOURCE_ID:
            return self.data.audio
        return None

    @property
    def selected_class_keys(self) -> frozenset[str]:
        """Return builtin YOLO classes that should expose binary sensors."""
        if self.data is None:
            return frozenset()
        return frozenset(
            identity
            for identity, item in self.data.class_catalog.items()
            if item.source_id == "builtin"
            if identity in self.tracked_class_keys
        )

    @property
    def firmware_update(self) -> FirmwareUpdateState:
        """Return the current firmware update state."""
        return self._firmware_update

    async def _async_fetch_latest_release_tag(self) -> str | None:
        """Read the public release tag when the device OTA check fails."""
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(3.0):
                async with session.get(
                    OTA_RELEASE_LATEST_API_URL,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "HomeAssistant-reCamera-Pro",
                    },
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
        except (TimeoutError, aiohttp.ClientError, OSError, ValueError) as err:
            _LOGGER.debug(
                "Unable to fetch latest GitHub release tag: %s",
                err,
            )
            return None
        tag = payload.get("tag_name") if isinstance(payload, dict) else None
        return str(tag).strip() if tag else None

    async def async_check_firmware_update(
        self,
        *,
        force: bool = False,
    ) -> FirmwareUpdateState:
        """Check the vendor OTA repository with a bounded cache."""
        if self._firmware_reboot is not None or (
            self._firmware_update.in_progress
            and self._firmware_update.operation != "external"
        ):
            # An owned install is still waiting for reboot confirmation.
            # A background check must not replace its local state.
            return self._firmware_update
        async with self._firmware_lock:
            if self._firmware_reboot is not None:
                return self._firmware_update
            now = datetime.now(UTC)
            current = self.data.info.firmware_version if self.data else None
            cached = self._firmware_update
            if (
                not force
                and cached.last_checked is not None
                and (now - cached.last_checked).total_seconds()
                < OTA_CHECK_INTERVAL_SECONDS
                and not cached.in_progress
            ):
                return cached

            try:
                async with asyncio.timeout(4.5):
                    response = await self.client.async_check_firmware_update(
                        OTA_RELEASE_URL
                    )
            except (
                TimeoutError,
                RecameraConnectionError,
                RecameraProtocolError,
            ) as err:
                # The device may be rate-limited or unable to reach GitHub.
                # The public release page still lets HA show the published
                # version without treating the installed version as latest.
                published = await self._async_fetch_latest_release_tag()
                if published is None:
                    if isinstance(err, TimeoutError):
                        raise RecameraConnectionError("firmware_check_timeout") from err
                    raise
                installed = str(current or "").strip() or None
                self._firmware_update = FirmwareUpdateState(
                    installed_version=installed,
                    latest_version=None,
                    published_version=published,
                    available=False,
                    in_progress=False,
                    status="check_failed",
                    last_checked=now,
                )
                self.async_update_listeners()
                return self._firmware_update
            available = bool(response["iUpdateAvailable"])
            installed = (
                str(response.get("sCurrentVersion") or current or "").strip() or None
            )
            reported_latest = str(response.get("sLatestVersion") or "").strip()
            latest = reported_latest or installed
            confirm_token = (
                str(response.get("sConfirmToken") or "").strip() or None
                if available
                else None
            )
            updating = bool(response.get("sUpdating"))
            self._firmware_update = FirmwareUpdateState(
                installed_version=installed,
                latest_version=latest,
                published_version=(reported_latest or None),
                target_version=(
                    reported_latest if available and reported_latest else None
                ),
                available=available,
                confirm_token=confirm_token,
                in_progress=updating,
                update_percentage=(
                    cached.update_percentage if cached.in_progress else None
                ),
                status=(
                    "updating" if updating else "available" if available else "idle"
                ),
                operation="external" if updating else None,
                last_checked=now,
            )
            self.async_update_listeners()
            return self._firmware_update

    async def _async_firmware_check_loop(self) -> None:
        """Refresh OTA metadata at startup and on the bounded interval."""
        while not self._stop.is_set():
            external_updating = (
                self._firmware_update.in_progress
                and self._firmware_update.operation == "external"
            )
            if self._firmware_reboot is None and (
                not self._firmware_update.in_progress or external_updating
            ):
                try:
                    if external_updating:
                        await self.async_check_firmware_update(force=True)
                    else:
                        await self.async_check_firmware_update()
                except asyncio.CancelledError:
                    raise
                except RecameraError as err:
                    _LOGGER.debug(
                        "Unable to refresh reCamera firmware state: %s",
                        err,
                    )
                except Exception:
                    _LOGGER.exception(
                        "Unexpected reCamera firmware state refresh error"
                    )
            delay = (
                45
                if (
                    self._firmware_update.in_progress
                    and self._firmware_update.operation == "external"
                )
                else OTA_CHECK_INTERVAL_SECONDS
            )
            await self._sleep(delay)

    async def async_install_firmware_update(
        self,
        progress_callback: Callable[[int | None], None] | None = None,
    ) -> None:
        """Download and apply the current firmware update."""
        async with self._firmware_lock:
            if self._firmware_update.in_progress:
                raise RecameraValidationError("firmware_busy")
            checked = await self._async_check_firmware_update_locked()
            if checked.in_progress:
                raise RecameraValidationError("firmware_busy")
            token = checked.confirm_token
            target_version = checked.target_version
            if not checked.available or not token:
                raise RecameraValidationError("firmware_no_update")
            if not target_version:
                raise RecameraProtocolError("firmware_target_unknown")

            self._firmware_update = replace(
                checked,
                in_progress=True,
                update_percentage=0,
                status="starting",
                operation="online",
            )
            self.async_update_listeners()
            if progress_callback:
                progress_callback(0)

            try:
                await self.client.async_start_firmware_update(token)
                deadline = (
                    asyncio.get_running_loop().time() + OTA_DOWNLOAD_TIMEOUT_SECONDS
                )
                while True:
                    if asyncio.get_running_loop().time() >= deadline:
                        _raise_firmware_download_timeout()
                    progress = await self.client.async_get_firmware_download_progress()
                    status = str(progress.get("sStatus") or "idle").strip().lower()
                    try:
                        percent = int(progress.get("iPercent") or 0)
                    except TypeError, ValueError:
                        percent = 0
                    percent = min(100, max(0, percent))
                    self._firmware_update = replace(
                        self._firmware_update,
                        update_percentage=percent,
                        status=status,
                    )
                    self.async_update_listeners()
                    if progress_callback:
                        progress_callback(percent)
                    if status == "success":
                        break
                    if status in {"fail", "failed", "error"}:
                        _raise_firmware_download_failed()
                    await asyncio.sleep(OTA_POLL_INTERVAL_SECONDS)

                self._firmware_update = replace(
                    self._firmware_update,
                    in_progress=True,
                    update_percentage=100,
                    status="applying",
                )
                self.async_update_listeners()
                submission_confirmed = await self.client.async_apply_firmware_update()
            except asyncio.CancelledError:
                self._firmware_update = replace(
                    self._firmware_update,
                    in_progress=False,
                    status="canceled",
                    operation=None,
                )
                self.async_update_listeners()
                raise
            except Exception as err:
                self._firmware_update = replace(
                    self._firmware_update,
                    in_progress=False,
                    status="failed",
                    operation=None,
                )
                self.async_update_listeners()
                self._async_publish_firmware_result(
                    success=False,
                    previous_version=(self._firmware_update.installed_version),
                    current_version=None,
                    operation="online",
                    error=type(err).__name__,
                )
                raise

            self._begin_firmware_reboot(
                "online",
                target_version,
                submission_confirmed=submission_confirmed,
            )

    async def _async_check_firmware_update_locked(
        self,
    ) -> FirmwareUpdateState:
        """Run a fresh OTA check while the caller owns the firmware lock."""
        response = await self.client.async_check_firmware_update(OTA_RELEASE_URL)
        current = self.data.info.firmware_version if self.data else None
        available = bool(response["iUpdateAvailable"])
        installed = (
            str(response.get("sCurrentVersion") or current or "").strip() or None
        )
        reported_latest = str(response.get("sLatestVersion") or "").strip()
        latest = reported_latest or installed
        confirm_token = (
            str(response.get("sConfirmToken") or "").strip() or None
            if available
            else None
        )
        updating = bool(response.get("sUpdating"))
        self._firmware_update = FirmwareUpdateState(
            installed_version=installed,
            latest_version=latest,
            published_version=(reported_latest or None),
            target_version=(reported_latest if available and reported_latest else None),
            available=available,
            confirm_token=confirm_token,
            in_progress=updating,
            status=("updating" if updating else "available" if available else "idle"),
            operation="external" if updating else None,
            last_checked=datetime.now(UTC),
        )
        self.async_update_listeners()
        return self._firmware_update

    async def async_capture_device_snapshot(
        self,
        output: str | None,
        *,
        request_id: str,
    ) -> dict[str, object]:
        """Capture one device snapshot for this service-call context."""
        return await self.capture_controller.async_capture_snapshot(
            output,
            request_id=request_id,
        )

    async def async_start_device_recording(
        self,
        *,
        output: str | None,
        duration: int,
        request_id: str,
    ) -> dict[str, object]:
        """Start one device recording for this service-call context."""
        return await self.capture_controller.async_start_recording(
            output,
            duration,
            request_id=request_id,
        )

    async def async_stop_device_capture(
        self,
        *,
        request_id: str,
    ) -> dict[str, object]:
        """Stop a recording owned by this integration instance."""
        return await self.capture_controller.async_stop_capture(
            request_id=request_id,
        )

    async def async_update_video_encode(
        self,
        stream: str,
        *,
        resolution: str | None = None,
        frame_rate: str | None = None,
        max_bitrate: int | None = None,
        gop: int | None = None,
        h264_profile: str | None = None,
        codec: str | None = None,
    ) -> None:
        """Update a Camera stream encoding configuration on the device."""
        if stream not in {"main", "sub"}:
            raise RecameraValidationError("invalid_video_stream")
        async with self._video_update_lock:
            stream_id = 0 if stream == "main" else 1
            updated = await self.client.async_update_stream_encode(
                stream_id,
                resolution=resolution,
                frame_rate=frame_rate,
                max_bitrate=max_bitrate,
                gop=gop,
                h264_profile=h264_profile,
                codec=codec,
            )
            stream_info = await self.client.async_get_stream(stream_id)
            if self.data is not None:
                profiles = {
                    key: {name: dict(value) for name, value in profile.items()}
                    for key, profile in self.data.media_profiles.items()
                }
                profiles.setdefault(stream, {})["encode"] = updated
                profiles[stream]["stream"] = stream_info
                self.async_set_updated_data(
                    replace(
                        self.data,
                        media_profiles=profiles,
                        stream_info=(
                            stream_info if stream == "sub" else self.data.stream_info
                        ),
                    )
                )

    async def async_set_detection_option(self, key: str, value: float) -> None:
        """Persist one YOLO runtime option without reloading the entry."""
        options = {**self.config_entry.options, key: value}
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)
        if key == CONF_VISUAL_CONFIDENCE:
            self.visual_min_confidence = float(value)
        elif key == CONF_VISUAL_CONFIRM:
            self.visual_confirm_seconds = float(value)
        elif key == CONF_AUDIO_CONFIDENCE:
            self.audio_min_confidence = float(value)
        elif key == CONF_CLASS_STALE_SECONDS:
            self.class_stale_seconds = float(value)
        elif key == CONF_VISUAL_COOLDOWN:
            self.visual_cooldown = float(value)
        elif key == CONF_AUDIO_COOLDOWN:
            self.audio_cooldown = float(value)
        self.async_update_listeners()

    def class_entity_unique_id(self, item: DetectedClass) -> str:
        """Return the stable class entity unique ID."""
        return f"{self.device_id}_class_{stable_class_token(item.key)}_active"

    async def async_setup(self) -> None:
        """Load catalog state and perform the first metadata refresh."""
        catalog = await self._async_load_class_catalog()
        try:
            await self.async_config_entry_first_refresh()
        except BaseException:
            await self.client.async_close()
            raise
        await self.capture_controller.async_restore()
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, class_catalog=catalog))
            if self.data.info.firmware_version:
                self._firmware_update = replace(
                    self._firmware_update,
                    installed_version=self.data.info.firmware_version,
                )
        self._websocket_task = self.hass.async_create_background_task(
            self._async_websocket_loop(),
            f"{DOMAIN}.{self.config_entry.entry_id}.websocket",
        )
        self._firmware_check_task = self.hass.async_create_background_task(
            self._async_firmware_check_loop(),
            f"{DOMAIN}.{self.config_entry.entry_id}.firmware_check",
        )
        self._stale_task = self.hass.async_create_background_task(
            self._async_expire_stale_state(),
            f"{DOMAIN}.{self.config_entry.entry_id}.stale_state",
        )
        self._unsub_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            self._async_handle_homeassistant_stop,
        )
        if self._firmware_reboot is not None:
            self._schedule_firmware_reboot_monitor()

    @callback
    def _async_handle_homeassistant_stop(self, _event: Any) -> None:
        """Cancel long-running work before Home Assistant final writes."""
        self._stop.set()
        for task in (
            getattr(self, "_websocket_task", None),
            getattr(self, "_connection_recovery_task", None),
            getattr(self, "_firmware_check_task", None),
            getattr(self, "_stale_task", None),
            getattr(self, "_firmware_reboot_task", None),
        ):
            if task is not None:
                task.cancel()

    async def _async_load_class_catalog(self) -> dict[str, DetectedClass]:
        """Load persisted builtin YOLO classes only."""
        stored = await self._store.async_load() or {}
        self._cached_stream_info = {
            stream: dict(value)
            for stream, value in (stored.get("media_streams") or {}).items()
            if stream in {"main", "sub"} and isinstance(value, dict)
        }
        self._restore_firmware_reboot(stored)
        catalog: dict[str, DetectedClass] = {}
        for item in stored.get("class_catalog") or []:
            if not isinstance(item, dict):
                continue
            detected_class = DetectedClass.from_dict(item)
            if detected_class is not None:
                catalog[detected_class.key] = detected_class
        for item in stored.get("discovered_classes") or []:
            if not isinstance(item, list) or len(item) != 2:
                continue
            detected_class = DetectedClass.from_dict(
                {
                    "source_id": item[0],
                    "class_name": item[1],
                    "task_type": "detection",
                }
            )
            if detected_class is not None:
                catalog.setdefault(detected_class.key, detected_class)
        return catalog

    @callback
    def _restore_firmware_reboot(self, stored: dict[str, Any]) -> None:
        """Restore a firmware reboot that was pending across HA restart."""
        pending = stored.get("firmware_reboot")
        if not isinstance(pending, dict):
            return
        from_version = str(pending.get("from_version") or "").strip()
        operation = str(pending.get("operation") or "").strip()
        if operation not in {"local", "online"}:
            return
        self._firmware_reboot = {
            "from_version": from_version or None,
            "operation": operation,
            "started_at": str(pending.get("started_at") or ""),
            "unreachable_seen": pending.get("unreachable_seen") is True,
            "target_version": str(pending.get("target_version") or "").strip() or None,
        }
        self._firmware_update = replace(
            self._firmware_update,
            in_progress=True,
            status="rebooting",
            operation=operation,
            target_version=(str(pending.get("target_version") or "").strip() or None),
        )

    @callback
    def _begin_firmware_reboot(
        self,
        operation: str,
        target_version: str | None = None,
        *,
        submission_confirmed: bool = True,
    ) -> None:
        """Track one accepted firmware install until the device reconnects."""
        previous = (
            self.data.info.firmware_version
            if self.data is not None
            else self._firmware_update.installed_version
        )
        self._firmware_reboot = {
            "from_version": previous,
            "operation": operation,
            "started_at": datetime.now(UTC).isoformat(),
            "unreachable_seen": False,
            "target_version": target_version,
        }
        self._firmware_update = replace(
            self._firmware_update,
            available=False,
            confirm_token=None,
            in_progress=True,
            update_percentage=100,
            status=("rebooting" if submission_confirmed else "submission_unconfirmed"),
            operation=operation,
            target_version=target_version,
        )
        self.async_update_listeners()
        store = getattr(self, "_store", None)
        save = getattr(store, "async_delay_save", None)
        if save is not None:
            save(lambda: self._store_payload(), 0)
        self._schedule_firmware_reboot_monitor()

    @callback
    def _schedule_firmware_reboot_monitor(self) -> None:
        """Monitor device reconnection promptly after firmware install."""
        hass = getattr(self, "hass", None)
        create_task = getattr(hass, "async_create_background_task", None)
        task = getattr(self, "_firmware_reboot_task", None)
        if create_task is None or (task is not None and not task.done()):
            return
        self._firmware_reboot_task = create_task(
            self._async_monitor_firmware_reboot(),
            f"{DOMAIN}.{self.config_entry.entry_id}.firmware_reboot",
        )

    async def _async_monitor_firmware_reboot(self) -> None:
        """Wait for the device to return and publish the OTA result."""
        pending = self._firmware_reboot
        if pending is None:
            return
        previous = pending.get("from_version")
        operation = pending.get("operation")
        target = pending.get("target_version")
        if operation == "online" and not target:
            self._finish_firmware_reboot(
                None,
                success=False,
                error="firmware_target_unknown",
                refresh_data=False,
            )
            return
        started_at = _firmware_started_at(pending.get("started_at"))
        if started_at is None:
            self._finish_firmware_reboot(
                None,
                success=False,
                error="firmware_reboot_state_invalid",
                refresh_data=False,
            )
            return
        elapsed = max(
            0.0,
            (datetime.now(UTC) - started_at).total_seconds(),
        )
        remaining = max(0.0, FIRMWARE_REBOOT_TIMEOUT_SECONDS - elapsed)
        deadline = asyncio.get_running_loop().time() + remaining
        unreachable = pending.get("unreachable_seen") is True
        try:
            while True:
                if asyncio.get_running_loop().time() >= deadline:
                    self._firmware_reboot_task = None
                    self._finish_firmware_reboot(
                        None,
                        success=False,
                        error="device_reconnect_timeout",
                        refresh_data=False,
                    )
                    return
                await asyncio.sleep(FIRMWARE_RECONNECT_POLL_SECONDS)
                try:
                    info = await self.client.async_get_device_info()
                except RecameraConnectionError:
                    unreachable = True
                    if self._firmware_reboot is not None:
                        self._firmware_reboot["unreachable_seen"] = True
                        store = getattr(self, "_store", None)
                        save = getattr(store, "async_delay_save", None)
                        if save is not None:
                            save(lambda: self._store_payload(), 0)
                    continue
                except RecameraError as err:
                    _LOGGER.debug(
                        "Firmware reconnect check returned %s: %s",
                        type(err).__name__,
                        err,
                    )
                    continue
                current = info.firmware_version
                if not current:
                    continue
                if operation == "online":
                    if _normalized_firmware_version(
                        current
                    ) == _normalized_firmware_version(target):
                        self._firmware_reboot_task = None
                        self._finish_firmware_reboot(
                            current,
                            success=True,
                            refresh_data=True,
                        )
                        return
                    if _normalized_firmware_version(
                        current
                    ) != _normalized_firmware_version(previous):
                        self._firmware_reboot_task = None
                        self._finish_firmware_reboot(
                            current,
                            success=False,
                            error="firmware_target_mismatch",
                            refresh_data=True,
                        )
                        return
                    continue
                if _normalized_firmware_version(
                    current
                ) != _normalized_firmware_version(previous):
                    self._firmware_reboot_task = None
                    self._finish_firmware_reboot(
                        current,
                        success=True,
                        refresh_data=True,
                    )
                    return
                if unreachable:
                    self._firmware_reboot_task = None
                    self._finish_firmware_reboot(
                        current,
                        success=False,
                        error="firmware_version_unconfirmed",
                        refresh_data=True,
                    )
                    return
        finally:
            if self._firmware_reboot_task is asyncio.current_task():
                self._firmware_reboot_task = None

    @callback
    def _finish_firmware_reboot(
        self,
        current_version: str | None,
        *,
        success: bool,
        error: str | None = None,
        refresh_data: bool = False,
    ) -> None:
        """Publish one terminal firmware result and clear pending state."""
        pending = self._firmware_reboot
        if pending is None:
            return
        previous = pending.get("from_version")
        operation = pending.get("operation")
        self._firmware_reboot = None
        self._firmware_update = replace(
            self._firmware_update,
            installed_version=(
                current_version or self._firmware_update.installed_version
            ),
            latest_version=(
                current_version
                if success and current_version
                else self._firmware_update.latest_version
            ),
            target_version=None,
            available=False,
            confirm_token=None,
            in_progress=False,
            update_percentage=None,
            status=(
                "completed"
                if success
                else (
                    "unconfirmed"
                    if error == "firmware_version_unconfirmed"
                    else "failed"
                )
            ),
            operation=None,
            last_checked=datetime.now(UTC),
        )
        if current_version:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_SW_VERSION: current_version,
                },
            )
        if refresh_data and self.data is not None and current_version:
            self.async_set_updated_data(
                replace(
                    self.data,
                    info=replace(
                        self.data.info,
                        firmware_version=current_version,
                    ),
                )
            )
        store = getattr(self, "_store", None)
        save = getattr(store, "async_delay_save", None)
        if save is not None:
            save(lambda: self._store_payload(), 0)
        self.async_update_listeners()
        self._async_publish_firmware_result(
            success=success,
            previous_version=previous,
            current_version=current_version,
            operation=operation,
            error=error,
        )
        task = getattr(self, "_firmware_reboot_task", None)
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        self._firmware_reboot_task = None
        if task is not None and task is not current_task:
            task.cancel()

    @callback
    def _async_publish_firmware_result(
        self,
        *,
        success: bool,
        previous_version: str | None,
        current_version: str | None,
        operation: str | None,
        error: str | None = None,
    ) -> None:
        """Notify the user and fire an automation event for OTA completion."""
        hass = getattr(self, "hass", None)
        if hass is None:
            return
        bus = getattr(hass, "bus", None)
        if bus is not None:
            bus.async_fire(
                EVENT_FIRMWARE_UPDATE_COMPLETED,
                {
                    "device_id": self.device_id,
                    "entry_id": self.config_entry.entry_id,
                    "success": success,
                    "operation": operation,
                    "previous_version": previous_version,
                    "current_version": current_version,
                    "error": error,
                },
            )
        if not hasattr(hass, "services"):
            return
        options = getattr(getattr(self, "config_entry", None), "options", None) or {}
        configured_language = str(options.get(CONF_LANGUAGE) or "").strip()
        active_language = (
            configured_language
            if configured_language in {"en", "zh-Hans"}
            else str(getattr(hass.config, "language", "") or "")
        )
        zh = active_language.lower().startswith("zh")
        title = "reCamera Pro 固件更新" if zh else "reCamera Pro firmware"
        if success:
            if previous_version and current_version:
                message = (
                    f"固件更新完成，设备已重新连接："
                    f"{previous_version} → {current_version}。"
                    if zh
                    else f"Firmware update completed and the device "
                    f"reconnected: {previous_version} → {current_version}."
                )
            else:
                message = (
                    "固件更新完成，设备已重新连接。"
                    if zh
                    else "Firmware update completed and the device reconnected."
                )
        else:
            message = (
                f"固件更新失败：{error or '设备未能重新连接'}。"
                if zh
                else f"Firmware update failed: "
                f"{error or 'the device did not reconnect'}."
            )
        persistent_notification.async_create(
            hass,
            message,
            title=title,
            notification_id=(f"{DOMAIN}_{self.config_entry.entry_id}_firmware"),
        )

    def _candidate_identity_matches(self, probe: Any) -> bool:
        """Require a fallback host to expose the configured hardware identity."""
        entry = getattr(self, "config_entry", None)
        if entry is None:
            return False
        return not probe_identity_mismatch(
            entry.data,
            getattr(entry, "unique_id", None),
            probe.info,
        )

    async def _async_try_discovery_fallback(
        self,
        attempted: set[str],
    ) -> bool:
        """Switch to one authenticated alternate host from mDNS."""
        entry = getattr(self, "config_entry", None)
        if entry is None:
            return False
        data = getattr(entry, "data", {}) or {}
        current_host = str(getattr(self.client, "host", "") or "")
        candidates = recoverable_discovery_candidates(data, current_host)
        for host in candidates:
            if host in attempted:
                continue
            attempted.add(host)
            try:
                probe = await async_probe_device(
                    host,
                    str(data.get(CONF_USERNAME, "admin")),
                    str(data.get(CONF_PASSWORD, "")),
                )
            except RecameraError:
                continue
            except Exception:
                _LOGGER.exception(
                    "Unexpected reCamera candidate probe error for %s",
                    host,
                )
                continue

            if not self._candidate_identity_matches(probe):
                updated = dict(data)
                updated[CONF_DISCOVERY_CANDIDATES] = drop_discovery_candidate(
                    data, host
                )
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=updated,
                )
                data = updated
                continue

            await self._close_websocket()
            await self.client.async_close()
            self.connection_generation = getattr(self, "connection_generation", 0) + 1
            self.client.host = host
            updated = dict(data)
            updated[CONF_HOST] = host
            updated[CONF_DISCOVERY_CANDIDATES] = merge_discovery_candidate(data, host)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated,
            )
            _LOGGER.info(
                "reCamera discovery fallback switched %s -> %s",
                current_host or "unknown",
                host,
            )
            return True
        return False

    @override
    async def _async_update_data(self) -> RecameraRuntimeData:
        """Refresh metadata and non-blocking capability information."""
        previous = self.data
        if not isinstance(getattr(self, "_cached_stream_info", None), dict):
            self._cached_stream_info = {}
        motion_generation = getattr(self, "_motion_generation", 0)

        async def async_fetch_primary() -> tuple[Any, Any]:
            return await asyncio.gather(
                self.client.async_get_device_info(),
                self.client.async_get_capabilities(),
                return_exceptions=True,
            )

        info_result, capabilities_result = await async_fetch_primary()
        attempted: set[str] = set()
        while isinstance(
            info_result,
            (
                RecameraAuthenticationError,
                RecameraConnectionError,
                RecameraProtocolError,
            ),
        ) and await self._async_try_discovery_fallback(attempted):
            info_result, capabilities_result = await async_fetch_primary()
        if isinstance(info_result, RecameraAuthenticationError):
            raise ConfigEntryAuthFailed("invalid_auth") from info_result
        if isinstance(info_result, BaseException):
            raise UpdateFailed(str(info_result)) from info_result
        info = info_result
        capabilities = dict(previous.capabilities) if previous is not None else {}
        if isinstance(capabilities_result, RecameraAuthenticationError):
            raise ConfigEntryAuthFailed("invalid_auth") from capabilities_result
        if isinstance(capabilities_result, BaseException):
            _LOGGER.debug(
                "Unable to refresh camera capabilities: %s",
                capabilities_result,
            )
        else:
            capabilities = capabilities_result

        media_profiles = (
            {
                key: {name: dict(value) for name, value in profile.items()}
                for key, profile in previous.media_profiles.items()
            }
            if previous is not None
            else {}
        )
        media_errors: dict[str, str] = {}
        stream_cache_changed = False
        media_requests: list[tuple[str, str, Awaitable[Any]]] = []
        for stream_name, stream_id in (("main", 0), ("sub", 1)):
            media_profiles.setdefault(stream_name, {})
            media_requests.extend(
                (
                    (
                        stream_name,
                        "stream",
                        self.client.async_get_stream(stream_id),
                    ),
                    (
                        stream_name,
                        "encode",
                        self.client.async_get_stream_encode(stream_id),
                    ),
                )
            )
        media_results = await asyncio.gather(
            *(request for _, _, request in media_requests),
            return_exceptions=True,
        )
        for (stream_name, item_name, _), result in zip(
            media_requests,
            media_results,
            strict=True,
        ):
            profile = media_profiles.setdefault(stream_name, {})
            if isinstance(result, RecameraAuthenticationError):
                raise ConfigEntryAuthFailed("invalid_auth") from result
            if isinstance(result, BaseException):
                media_errors[f"{stream_name}.{item_name}"] = type(result).__name__
                if item_name == "stream":
                    cached = (
                        profile.get("stream")
                        or self._cached_stream_info.get(stream_name)
                        or {}
                    )
                    profile["stream"] = dict(cached)
                else:
                    profile[item_name] = {}
                _LOGGER.debug(
                    "Unable to refresh %s %s metadata: %s",
                    stream_name,
                    item_name,
                    result,
                )
            else:
                profile[item_name] = result
                if item_name == "stream" and isinstance(result, dict):
                    cached = dict(result)
                    if self._cached_stream_info.get(stream_name) != cached:
                        self._cached_stream_info[stream_name] = cached
                        stream_cache_changed = True
        stream_info = dict(media_profiles.get("sub", {}).get("stream") or {})
        if stream_cache_changed:
            store = getattr(self, "_store", None)
            if store is not None:
                store.async_delay_save(
                    lambda: self._store_payload(),
                    30,
                )
        previous_motion = (
            self.data.motion if self.data is not None else MotionDetectionState()
        )
        if previous_motion.transitioning:
            refreshed_motion = previous_motion
        else:
            refreshed_motion = await self._async_refresh_motion_state(previous_motion)
            if motion_generation != getattr(self, "_motion_generation", 0):
                refreshed_motion = (
                    self.data.motion if self.data is not None else previous_motion
                )
        latest = self.data
        if latest is None:
            return RecameraRuntimeData(
                info=info,
                capabilities=capabilities,
                stream_info=stream_info,
                media_profiles=media_profiles,
                media_errors=media_errors,
                motion=refreshed_motion,
            )
        motion = replace(
            latest.motion,
            installed=refreshed_motion.installed,
            running=refreshed_motion.running,
            motion=(latest.motion.motion if refreshed_motion.running else None),
            reason=refreshed_motion.reason,
            config=refreshed_motion.config,
            app_health=refreshed_motion.app_health,
            error=refreshed_motion.error,
            last_confirmed=refreshed_motion.last_confirmed,
            config_health=refreshed_motion.config_health,
            config_error=refreshed_motion.config_error,
            config_last_confirmed=(refreshed_motion.config_last_confirmed),
        )
        return replace(
            latest,
            info=info,
            capabilities=capabilities,
            stream_info=stream_info,
            media_profiles=media_profiles,
            media_errors=media_errors,
            motion=motion,
        )

    async def _async_refresh_motion_state(
        self,
        motion: MotionDetectionState,
    ) -> MotionDetectionState:
        """Refresh AppMgr lifecycle and motion configuration."""
        try:
            appmgr = await self.client.async_get_appmgr_list()
        except RecameraError as err:
            _LOGGER.warning(
                "Unable to refresh motion-detect app state: %s",
                err,
            )
            return replace(
                motion,
                reason="appmgr_unavailable",
                app_health=SOURCE_UNAVAILABLE,
                error=type(err).__name__,
            )
        app = next(
            (
                item
                for item in appmgr.get("apps") or []
                if item.get("id") == MOTION_APP_ID
            ),
            None,
        )
        if app is None:
            return MotionDetectionState(
                system_app=motion.system_app,
                system_source_confirmed=(motion.system_source_confirmed),
                reason="motion_app_not_installed",
                app_health=SOURCE_AVAILABLE,
                last_confirmed=datetime.now(UTC),
            )
        running = app.get("running") is True or app.get("observed_state") == "running"
        app_type = app.get("app_type", app.get("type"))
        source = app.get("source")
        source_kind = app.get("source_kind")
        if source_kind is None and isinstance(source, dict):
            source_kind = source.get("kind")
        metadata_marks_system = (
            app.get("system") is True
            or app.get("system_app") is True
            or app_type in {"builtin", "system"}
            or source_kind in {"builtin", "system"}
        )
        metadata_has_app_type = app_type is not None or source_kind is not None
        if metadata_marks_system:
            system_app = True
            system_source_confirmed = True
        elif metadata_has_app_type:
            system_app = False
            system_source_confirmed = True
        else:
            system_app = motion.system_app
            system_source_confirmed = motion.system_source_confirmed
        motion = replace(
            motion,
            installed=True,
            running=running,
            system_app=system_app,
            system_source_confirmed=system_source_confirmed,
            motion=motion.motion if running else None,
            reason=app.get("state_reason"),
            app_health=SOURCE_AVAILABLE,
            error=None,
            last_confirmed=datetime.now(UTC),
        )
        try:
            config_values = await self._async_read_motion_config_values()
            motion = replace(
                motion,
                config=config_values,
                config_health=SOURCE_AVAILABLE,
                config_error=None,
                config_last_confirmed=datetime.now(UTC),
            )
        except RecameraError as err:
            _LOGGER.debug(
                "Unable to refresh motion-detect config: %s",
                err,
            )
            motion = replace(
                motion,
                config_health=SOURCE_UNAVAILABLE,
                config_error=type(err).__name__,
            )
        return motion

    async def _async_read_motion_config_values(self) -> dict[str, Any]:
        """Read motion configuration, tolerating a brief app reload."""
        last_error: RecameraError | None = None
        for attempt in range(3):
            try:
                response = await self.client.async_get_appmgr_config(MOTION_APP_ID)
                values = response.get("values")
                if not isinstance(values, dict):
                    raise RecameraProtocolError("invalid_appmgr_response")
                return dict(values)
            except RecameraError as err:
                last_error = err
                if attempt < 2:
                    await asyncio.sleep(0.5)
        assert last_error is not None
        raise last_error

    async def async_set_motion_detection(self, enabled: bool) -> None:
        """Start or stop the motion-detect App and publish observed state."""
        async with self._motion_lock:
            if self.data is None or not self.data.motion.installed:
                raise RecameraValidationError("motion_app_not_installed")
            if self.data.motion.transitioning:
                raise RecameraValidationError("motion_transition_in_progress")
            previous_motion = self.data.motion
            self._motion_generation = getattr(self, "_motion_generation", 0) + 1
            transition_started = datetime.now(UTC)
            pending_motion = replace(
                previous_motion,
                running=enabled,
                motion=(
                    previous_motion.motion
                    if enabled and previous_motion.running
                    else None
                ),
                transitioning=True,
                target_running=enabled,
                transition_started_at=transition_started,
                transition_error=None,
                error=None,
            )
            self.async_set_updated_data(replace(self.data, motion=pending_motion))
            try:
                async with asyncio.timeout(MOTION_TRANSITION_TIMEOUT_SECONDS):
                    if enabled:
                        await self.client.async_start_app(
                            MOTION_APP_ID,
                            legacy_fallback=previous_motion.system_app,
                        )
                    else:
                        await self.client.async_stop_app(
                            MOTION_APP_ID,
                            legacy_fallback=previous_motion.system_app,
                        )
                    app = await self._async_confirm_motion_app_state(enabled)
            except TimeoutError as err:
                failure = RecameraProtocolError("motion_transition_timeout")
                motion = replace(
                    self.data.motion,
                    running=previous_motion.running,
                    motion=(
                        previous_motion.motion if previous_motion.running else None
                    ),
                    transitioning=False,
                    target_running=None,
                    transition_started_at=transition_started,
                    transition_error=failure.translation_key,
                    app_health=SOURCE_UNAVAILABLE,
                    error=failure.translation_key,
                )
                self.async_set_updated_data(replace(self.data, motion=motion))
                raise failure from err
            except RecameraError as err:
                motion = replace(
                    self.data.motion,
                    running=previous_motion.running,
                    motion=(
                        previous_motion.motion if previous_motion.running else None
                    ),
                    transitioning=False,
                    target_running=None,
                    transition_started_at=transition_started,
                    transition_error=err.translation_key,
                    app_health=SOURCE_UNAVAILABLE,
                    error=err.translation_key,
                )
                self.async_set_updated_data(replace(self.data, motion=motion))
                raise
            except asyncio.CancelledError:
                error = "motion_transition_cancelled"
                motion = replace(
                    self.data.motion,
                    transitioning=False,
                    target_running=None,
                    transition_started_at=transition_started,
                    transition_error=error,
                    app_health=SOURCE_UNKNOWN,
                    error=error,
                )
                self.async_set_updated_data(replace(self.data, motion=motion))
                raise
            running = (
                app.get("running") is True or app.get("observed_state") == "running"
            )
            motion = replace(
                self.data.motion,
                running=running,
                motion=self.data.motion.motion if running else None,
                reason=app.get("state_reason"),
                transitioning=False,
                target_running=None,
                transition_started_at=transition_started,
                transition_error=None,
                app_health=SOURCE_AVAILABLE,
                error=None,
                last_confirmed=datetime.now(UTC),
            )
            self.async_set_updated_data(replace(self.data, motion=motion))

    async def _async_confirm_motion_app_state(
        self,
        expected_running: bool,
    ) -> dict[str, Any]:
        """Confirm the App lifecycle state from the authoritative AppMgr list."""
        for attempt in range(3):
            appmgr = await self.client.async_get_appmgr_list()
            app = next(
                (item for item in appmgr["apps"] if item.get("id") == MOTION_APP_ID),
                None,
            )
            if app is None:
                raise RecameraValidationError("motion_app_not_installed")
            running = (
                app.get("running") is True or app.get("observed_state") == "running"
            )
            if running == expected_running:
                return app
            if attempt < 2:
                await asyncio.sleep(0.2)
        raise RecameraProtocolError("motion_state_not_confirmed")

    async def async_get_motion_detection_config(self) -> dict[str, Any]:
        """Return the motion-detect App's current validated config."""
        if self.data is None or not self.data.motion.installed:
            raise RecameraValidationError("motion_app_not_installed")
        try:
            values = await self._async_read_motion_config_values()
        except RecameraError as err:
            self.async_set_updated_data(
                replace(
                    self.data,
                    motion=replace(
                        self.data.motion,
                        config_health=SOURCE_UNAVAILABLE,
                        config_error=type(err).__name__,
                    ),
                )
            )
            raise
        self.async_set_updated_data(
            replace(
                self.data,
                motion=replace(
                    self.data.motion,
                    config=dict(values),
                    config_health=SOURCE_AVAILABLE,
                    config_error=None,
                    config_last_confirmed=datetime.now(UTC),
                ),
            )
        )
        return values

    async def async_update_motion_detection_config(
        self,
        config: dict[str, int | float],
    ) -> None:
        """Apply motion-detect analysis settings and verify the readback."""
        async with self._motion_lock:
            if self.data is None or not self.data.motion.installed:
                raise RecameraValidationError("motion_app_not_installed")
            if (
                self.data.motion.app_health != SOURCE_AVAILABLE
                or self.data.motion.config_health != SOURCE_AVAILABLE
            ):
                raise RecameraValidationError("motion_config_unavailable")
            try:
                response = await self.client.async_update_appmgr_config(
                    MOTION_APP_ID,
                    config,
                )
                applied = response.get("config")
                if not isinstance(applied, dict):
                    raise RecameraProtocolError("invalid_appmgr_response")
                readback = await self._async_read_motion_config_values()
                for key, expected in config.items():
                    try:
                        actual = float(readback[key])
                    except (KeyError, TypeError, ValueError) as err:
                        raise RecameraProtocolError(
                            "motion_config_not_applied"
                        ) from err
                    if abs(actual - float(expected)) > 1e-6:
                        raise RecameraProtocolError("motion_config_not_applied")
            except RecameraError as err:
                try:
                    refreshed = await self._async_read_motion_config_values()
                except RecameraError:
                    refreshed = None
                self.async_set_updated_data(
                    replace(
                        self.data,
                        motion=replace(
                            self.data.motion,
                            config=(
                                refreshed
                                if refreshed is not None
                                else self.data.motion.config
                            ),
                            config_health=(
                                SOURCE_AVAILABLE
                                if refreshed is not None
                                else SOURCE_UNAVAILABLE
                            ),
                            config_error=(
                                None if refreshed is not None else type(err).__name__
                            ),
                            config_last_confirmed=(
                                datetime.now(UTC)
                                if refreshed is not None
                                else self.data.motion.config_last_confirmed
                            ),
                        ),
                    )
                )
                raise
            now = datetime.now(UTC)
            motion = replace(
                self.data.motion,
                config=readback,
                config_health=SOURCE_AVAILABLE,
                config_error=None,
                config_last_confirmed=now,
            )
            self.async_set_updated_data(replace(self.data, motion=motion))

    @callback
    def _schedule_connection_recovery(self) -> None:
        """Refresh immediately after transport loss when alternates exist."""
        entry = getattr(self, "config_entry", None)
        if entry is None or self._stop.is_set():
            return
        current_host = str(getattr(self.client, "host", "") or "")
        if not valid_discovery_candidates(entry.data, current_host):
            return
        task = self._connection_recovery_task
        if task is not None and not task.done():
            return
        self._connection_recovery_task = self.hass.async_create_background_task(
            self._async_recover_connection(),
            (f"{DOMAIN}.{self.config_entry.entry_id}.connection_recovery"),
        )

    async def _async_recover_connection(self) -> None:
        """Run one single-flight recovery refresh after transport loss."""
        try:
            await self._sleep(0.25)
            if self._stop.is_set():
                return
            await self.async_refresh()
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Unexpected reCamera connection recovery error")
        finally:
            self._connection_recovery_task = None

    async def _async_websocket_loop(self) -> None:
        """Keep the authenticated Result Hub connection alive."""
        retry = WEBSOCKET_RETRY_MIN
        while not self._stop.is_set():
            retry_after_disconnect = True
            recover_connection = False
            try:
                websocket = await self.client.async_open_websocket(
                    DIRECT_RESULTS_WS_PATH
                )
                self._websocket = websocket
                await websocket.send_json(DIRECT_RESULTS_SUBSCRIBE)
                self._set_websocket_connected(True)
                connected_at = time.monotonic()
                retry_after_disconnect = False
                async for message in websocket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        self._handle_websocket_text(message.data)
                    elif message.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        recover_connection = True
                        break
                if time.monotonic() - connected_at >= 15.0:
                    retry = WEBSOCKET_RETRY_MIN
                else:
                    retry_after_disconnect = True
                recover_connection = True
            except asyncio.CancelledError:
                raise
            except RecameraAuthenticationError:
                self._set_websocket_connected(False)
                self._start_reauth()
                await self._sleep(WEBSOCKET_RETRY_MAX)
                continue
            except (RecameraConnectionError, aiohttp.ClientError, OSError) as err:
                retry_after_disconnect = True
                recover_connection = True
                _LOGGER.debug("reCamera websocket disconnected: %s", err)
            except Exception:
                retry_after_disconnect = True
                recover_connection = True
                _LOGGER.exception("Unexpected reCamera websocket error")
            finally:
                self._set_websocket_connected(False)
                await self._close_websocket()
            if self._stop.is_set():
                break
            if recover_connection:
                self._schedule_connection_recovery()
            if not retry_after_disconnect:
                _LOGGER.debug("reCamera websocket closed normally")
            await self._sleep(retry)
            retry = min(retry * 2, WEBSOCKET_RETRY_MAX)

    def _handle_websocket_text(self, raw: str) -> None:
        """Process only builtin YOLO frames and status messages."""
        try:
            payload = json.loads(raw)
        except ValueError:
            _LOGGER.warning("Ignoring malformed reCamera Result Hub JSON")
            return
        if not isinstance(payload, dict) or self.data is None:
            return

        now = datetime.now(UTC)
        message_type = payload.get("type")
        if message_type in {"hello", "snapshot"}:
            self.async_set_updated_data(
                replace(
                    self.data,
                    stream_ready=True,
                    last_stream_message=now,
                )
            )
            return

        source = payload.get("source") or {}
        source_id = str(source.get("id") or "") if isinstance(source, dict) else ""
        if source_id == MOTION_APP_ID:
            self._handle_motion_message(message_type, payload, now)
            return
        if source_id not in {"builtin", AUDIO_SOURCE_ID}:
            return

        if message_type == "source_invalidated":
            self._handle_source_status(
                SourceStatusRecord(source_id, SOURCE_UNAVAILABLE, "source_invalidated"),
                now,
            )
            return
        status = normalize_source_status(payload)
        if status is not None:
            self._handle_source_status(status, now)
            return
        if message_type != "frame":
            return

        parsed = parse_result_hub_message(payload, now)
        if parsed.error is not None:
            self._process_source_error(source_id, parsed.error, now)
            return
        self._process_source(source_id, parsed.observations, now)

    def _handle_motion_message(
        self,
        message_type: object,
        payload: dict[str, Any],
        received_at: datetime,
    ) -> None:
        """Update motion state from motion-detect App events."""
        if self.data is None:
            return
        if self.data.motion.transitioning:
            return
        if message_type == "source_invalidated":
            motion = replace(
                self.data.motion,
                running=False,
                motion=None,
                reason="source_invalidated",
                app_health=SOURCE_UNAVAILABLE,
                error="source_invalidated",
            )
            self.async_set_updated_data(replace(self.data, motion=motion))
            return
        if message_type not in {"frame", "event"}:
            return

        source = payload.get("source")
        if not isinstance(source, dict):
            return
        if source.get("kind") == "system":
            if self.data.motion.system_app or (
                not self.data.motion.system_source_confirmed
                and self._is_authoritative_system_summary(
                    source,
                    payload,
                )
            ):
                self._handle_system_motion_summary(
                    payload,
                    received_at,
                )
            return
        if self.data.motion.system_app:
            # Firmware system Apps use their in-process summary as the
            # authoritative state. Ignore stale app envelopes.
            return
        if not self.data.motion.running:
            # AppMgr lifecycle is authoritative. Frames already queued by a
            # stopped App must not turn the HA switch back on.
            return
        raw_events = payload.get("events")
        if not isinstance(raw_events, list):
            raw_events = []
        for event_index, event in enumerate(raw_events):
            if not isinstance(event, dict) or event.get("kind") != "motion_state":
                continue
            motion_value = event.get("motion")
            if type(motion_value) is not bool:
                continue
            event_identity = (
                event.get("event_id") or event.get("id") or event.get("seq")
            )
            if event_identity is None and payload.get("seq") is not None:
                event_identity = f"{payload['seq']}:{event_index}"
            if event_identity is not None:
                source_instance = (
                    source.get("instance_id")
                    or source.get("instance")
                    or source.get("id")
                )
                generation = source.get("generation")
                dedup_key = (
                    source_instance,
                    generation,
                    event.get("kind"),
                    event_identity,
                )
                if dedup_key in self._motion_seen_events:
                    continue
                self._motion_seen_events.append(dedup_key)
            try:
                score = float(event["score"])
                changed_ratio = float(event["changed_ratio"])
            except KeyError, TypeError, ValueError:
                continue
            changed_pixels = event.get("changed_pixels")
            try:
                changed_pixels = (
                    int(changed_pixels) if changed_pixels is not None else None
                )
            except TypeError, ValueError:
                changed_pixels = None
            motion = replace(
                self.data.motion,
                motion=motion_value,
                score=score,
                changed_ratio=changed_ratio,
                changed_pixels=changed_pixels,
                last_seen=received_at,
                reason=None,
                app_health=SOURCE_AVAILABLE,
                error=None,
                last_confirmed=received_at,
                event_id=(str(event_identity) if event_identity is not None else None),
                sequence=(
                    int(payload["seq"]) if isinstance(payload.get("seq"), int) else None
                ),
            )
            self.async_set_updated_data(replace(self.data, motion=motion))

    @staticmethod
    def _is_authoritative_system_summary(
        source: dict[str, Any],
        payload: dict[str, Any],
    ) -> bool:
        """Recognize V1.3.0 in-process summaries before AppMgr catches up."""
        if str(source.get("trust") or "").casefold() != "in-process":
            return False
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return False
        daemon_running = summary.get("daemon_running")
        if daemon_running is not None and type(daemon_running) is not bool:
            return False
        return type(summary.get("motion")) is bool

    @callback
    def _handle_system_motion_summary(
        self,
        payload: dict[str, Any],
        received_at: datetime,
    ) -> None:
        """Apply the firmware system App's authoritative motion summary."""
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return

        daemon_running = summary.get("daemon_running")
        motion_value = summary.get("motion")
        if daemon_running is not None and type(daemon_running) is not bool:
            return
        if daemon_running is not False and type(motion_value) is not bool:
            return

        sequence = payload.get("seq")
        if type(sequence) is not int:
            sequence = None
        source = payload.get("source") or {}
        source_instance = (
            source.get("instance") or source.get("id")
            if isinstance(source, dict)
            else None
        )
        if sequence is not None:
            dedup_key = (
                source_instance,
                source.get("generation") if isinstance(source, dict) else None,
                "system_motion_summary",
                sequence,
            )
            if dedup_key in self._motion_seen_events:
                return
            self._motion_seen_events.append(dedup_key)

        if daemon_running is False:
            motion = replace(
                self.data.motion,
                system_app=True,
                system_source_confirmed=True,
                running=False,
                motion=None,
                reason="daemon_stopped",
                app_health=SOURCE_AVAILABLE,
                error=None,
                last_seen=received_at,
                last_confirmed=received_at,
                event_id=(
                    f"evt:{MOTION_APP_ID}:system:{sequence}"
                    if sequence is not None
                    else None
                ),
                sequence=sequence,
            )
            self.async_set_updated_data(replace(self.data, motion=motion))
            return
        try:
            score = float(summary["score"])
        except KeyError, TypeError, ValueError:
            score = None
        try:
            changed_ratio = float(summary["changed_ratio"])
        except KeyError, TypeError, ValueError:
            changed_ratio = None
        changed_pixels = summary.get("changed_pixels")
        try:
            changed_pixels = int(changed_pixels) if changed_pixels is not None else None
        except TypeError, ValueError:
            changed_pixels = None
        motion = replace(
            self.data.motion,
            system_app=True,
            system_source_confirmed=True,
            running=True,
            motion=motion_value,
            score=score,
            changed_ratio=changed_ratio,
            changed_pixels=changed_pixels,
            last_seen=received_at,
            reason=None,
            app_health=SOURCE_AVAILABLE,
            error=None,
            last_confirmed=received_at,
            event_id=(
                f"evt:{MOTION_APP_ID}:system:{sequence}"
                if sequence is not None
                else None
            ),
            sequence=sequence,
        )
        self.async_set_updated_data(replace(self.data, motion=motion))

    def _process_source_error(
        self, source_id: str, error: str, received_at: datetime
    ) -> None:
        """Mark malformed source data unknown."""
        if self.data is None:
            return
        previous_state = (
            self.data.audio if source_id == AUDIO_SOURCE_ID else self.data.visual
        )
        updated_state = update_source_health(
            previous_state,
            health=SOURCE_UNKNOWN,
            reason=error,
            received_at=received_at,
            monotonic_now=asyncio.get_running_loop().time(),
        )
        if source_id == AUDIO_SOURCE_ID:
            updated_runtime = replace(
                self.data,
                audio=updated_state,
                last_stream_message=received_at,
            )
        else:
            updated_runtime = replace(
                self.data,
                visual=updated_state,
                last_stream_message=received_at,
            )
        self.async_set_updated_data(updated_runtime)

    def _record_classes(self, observations: list[ResultObservation]) -> None:
        """Persist newly observed builtin YOLO classes."""
        if self.data is None or not observations:
            return
        catalog = dict(self.data.class_catalog)
        changed = False
        for observation in observations:
            detected_class = observation.detected_class
            if catalog.get(detected_class.key) != detected_class:
                catalog[detected_class.key] = detected_class
                changed = True
        if changed:
            self.async_set_updated_data(replace(self.data, class_catalog=catalog))
            self._async_save_store(catalog)

    def _process_source(
        self,
        source_id: str,
        observations: list[ResultObservation],
        received_at: datetime,
    ) -> None:
        """Apply one visual YOLO or sound classification frame."""
        if self.data is None:
            return
        previous_state = (
            self.data.audio if source_id == AUDIO_SOURCE_ID else self.data.visual
        )
        self._record_classes(observations)
        monotonic_now = asyncio.get_running_loop().time()
        is_audio = source_id == AUDIO_SOURCE_ID
        updated_state, new_records, self._event_sequence = update_source_observations(
            previous_state,
            observations,
            received_at=received_at,
            monotonic_now=monotonic_now,
            confidence_threshold=(
                self.audio_min_confidence if is_audio else self.visual_min_confidence
            ),
            confirm_seconds=(0.0 if is_audio else self.visual_confirm_seconds),
            cooldown_seconds=(
                self.audio_cooldown if is_audio else self.visual_cooldown
            ),
            next_event_serial=self._event_sequence,
            history_limit=EVENT_HISTORY_LIMIT,
        )
        contextual_records: list[EventRecord] = []
        for record in new_records:
            context = new_event_context()
            contextual_records.append(replace(record, context=context))
        if contextual_records:
            by_serial = {record.serial: record for record in contextual_records}
            updated_state = replace(
                updated_state,
                events=tuple(
                    by_serial.get(record.serial, record)
                    for record in updated_state.events
                ),
            )
        if is_audio:
            runtime = replace(
                self.data,
                audio=updated_state,
                stream_ready=True,
                last_stream_message=received_at,
            )
        else:
            runtime = replace(
                self.data,
                visual=updated_state,
                stream_ready=True,
                last_stream_message=received_at,
            )
        active_changed = updated_state.active_classes != previous_state.active_classes
        summary_changed = (
            updated_state.summary_observation != previous_state.summary_observation
        )
        health_changed = (
            previous_state.health != updated_state.health
            or previous_state.reason != updated_state.reason
            or previous_state.clock_invalid != updated_state.clock_invalid
        )
        if new_records or active_changed or summary_changed or health_changed:
            self._last_summary_publish[source_id] = monotonic_now
            self.async_set_updated_data(runtime)
        else:
            self.data = runtime
        activity_event = getattr(self, "_activity_event", None)
        if activity_event is not None:
            activity_event.set()

    def _handle_source_status(
        self, status: SourceStatusRecord, received_at: datetime
    ) -> None:
        """Apply one source health without deleting event history."""
        if self.data is None:
            return
        previous_state = (
            self.data.audio if status.source_id == AUDIO_SOURCE_ID else self.data.visual
        )
        updated_state = update_source_health(
            previous_state,
            health=status.health,
            reason=status.reason,
            received_at=received_at,
            monotonic_now=asyncio.get_running_loop().time(),
        )
        if status.source_id == AUDIO_SOURCE_ID:
            updated_runtime = replace(
                self.data,
                audio=updated_state,
                last_stream_message=received_at,
            )
        else:
            updated_runtime = replace(
                self.data,
                visual=updated_state,
                last_stream_message=received_at,
            )
        self.async_set_updated_data(updated_runtime)

    def _set_websocket_connected(self, connected: bool) -> None:
        """Update transport and builtin YOLO availability."""
        if self.data is None:
            return
        visual_health = (
            self.data.visual.health
            if connected and self.data.visual.health == SOURCE_AVAILABLE
            else (SOURCE_UNKNOWN if connected else SOURCE_UNAVAILABLE)
        )
        audio_health = (
            self.data.audio.health
            if connected and self.data.audio.health == SOURCE_AVAILABLE
            else (SOURCE_UNKNOWN if connected else SOURCE_UNAVAILABLE)
        )
        visual = replace(
            self.data.visual,
            health=visual_health,
            reason=None,
            active_classes=set(),
            class_last_seen={},
            confirm_candidate_since={},
            confirm_candidate_last_seen={},
        )
        audio = replace(
            self.data.audio,
            health=audio_health,
            reason=None,
            active_classes=set(),
            class_last_seen={},
            confirm_candidate_since={},
            confirm_candidate_last_seen={},
        )
        motion = replace(
            self.data.motion,
            motion=None if not connected else self.data.motion.motion,
            reason=None if connected else "websocket_disconnected",
        )
        self.async_set_updated_data(
            replace(
                self.data,
                visual=visual,
                audio=audio,
                motion=motion,
                websocket_connected=connected,
                stream_ready=False if not connected else self.data.stream_ready,
            )
        )
        activity_event = getattr(self, "_activity_event", None)
        if activity_event is not None:
            activity_event.set()

    def _has_pending_expiration(self) -> bool:
        """Return whether any detection state currently requires 1s expiration checks."""
        if self.data is None:
            return False
        for state in (self.data.visual, self.data.audio):
            if (
                state.active_classes
                or state.confirm_candidate_since
                or (self.data.websocket_connected and state.health == SOURCE_AVAILABLE)
            ):
                return True
        return False

    async def _async_expire_stale_state(self) -> None:
        """Expire held YOLO classes and demote a silent stream."""
        activity_event = getattr(self, "_activity_event", None)
        while not self._stop.is_set():
            if activity_event is not None and not self._has_pending_expiration():
                activity_event.clear()
                if not self._has_pending_expiration():
                    stop_task = asyncio.create_task(self._stop.wait())
                    act_task = asyncio.create_task(activity_event.wait())
                    pending: set[asyncio.Task[Any]] = {stop_task, act_task}
                    try:
                        done, pending = await asyncio.wait(
                            pending,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for task in done:
                            task.result()
                    finally:
                        for task in pending:
                            task.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                    continue
            await self._sleep(1)
            if self._stop.is_set():
                break
            if self.data is None:
                continue
            now_monotonic = asyncio.get_running_loop().time()
            visual, visual_changed = expire_detection_state(
                self.data.visual,
                now_monotonic=now_monotonic,
                stale_seconds=self.class_stale_seconds,
                source_offline_seconds=SOURCE_OFFLINE_SECONDS,
                websocket_connected=self.data.websocket_connected,
            )
            audio, audio_changed = expire_detection_state(
                self.data.audio,
                now_monotonic=now_monotonic,
                stale_seconds=self.class_stale_seconds,
                source_offline_seconds=SOURCE_OFFLINE_SECONDS,
                websocket_connected=self.data.websocket_connected,
            )
            if visual_changed or audio_changed:
                self.async_set_updated_data(
                    replace(self.data, visual=visual, audio=audio)
                )

    def class_is_active(self, item: DetectedClass) -> bool:
        """Return whether a YOLO or sound class is currently active."""
        state = self.source_state(item.source_id)
        return bool(state and item.key in state.active_classes)

    def _stream_info_for(self, stream: str = "sub") -> dict[str, Any]:
        """Return cached stream description dict for one stream."""
        if self.data is None:
            return {}
        profile = self.data.media_profiles.get(stream) or {}
        stream_info = profile.get("stream") or {}
        if not stream_info and stream == "sub":
            stream_info = self.data.stream_info
        return stream_info if isinstance(stream_info, dict) else {}

    def has_stream_profile(self, stream: str = "sub") -> bool:
        """Return whether stream metadata with RTSP config is available."""
        stream_info = self._stream_info_for(stream)
        return isinstance(stream_info.get("rtsp"), dict)

    def is_stream_enabled(self, stream: str = "sub") -> bool:
        """Return whether RTSP streaming is enabled for one stream."""
        rtsp = self._stream_info_for(stream).get("rtsp") or {}
        return isinstance(rtsp, dict) and rtsp.get("iEnabled") == 1

    def register_stream_stop_callback(
        self, stream: str, stop_cb: Callable[[], Any]
    ) -> Callable[[], None]:
        """Register an async callback to stop HA stream consumers before disabling RTSP."""
        callbacks = self._stream_stop_callbacks.setdefault(stream, [])
        callbacks.append(stop_cb)

        def _unsub() -> None:
            registered = self._stream_stop_callbacks.get(stream)
            if registered and stop_cb in registered:
                registered.remove(stop_cb)

        return _unsub

    async def async_set_stream_enabled(
        self, stream: str, enabled: bool
    ) -> dict[str, Any]:
        """Enable or disable RTSP streaming for main/sub stream and refresh state."""
        stream_map = {"main": 0, "sub": 1}
        if stream not in stream_map:
            raise RecameraValidationError("invalid_video_stream")
        if not enabled:
            for stop_cb in list(
                getattr(self, "_stream_stop_callbacks", {}).get(stream, ())
            ):
                await stop_cb()
        stream_id = stream_map[stream]
        if hasattr(self.client, "async_set_rtsp_stream_enabled"):
            updated = await self.client.async_set_rtsp_stream_enabled(
                stream_id, enabled
            )
        else:
            current = await self.client.async_get_stream(stream_id)
            rtsp = current.get("rtsp") or {}
            desired = 1 if enabled else 0
            payload: dict[str, Any] = {
                key: dict(value) if isinstance(value, dict) else value
                for key, value in current.items()
            }
            payload["rtsp"] = {**rtsp, "iEnabled": desired}
            if enabled:
                for other_key in ("rtmp", "onvif", "mut" + "icast", "multicast"):
                    other = payload.get(other_key)
                    if isinstance(other, dict) and "iEnabled" in other:
                        payload[other_key] = {**other, "iEnabled": 0}
            await self.client.async_post_json(f"/video/{stream_id}/stream", payload)
            updated = await self.client.async_get_stream(stream_id)
        if not isinstance(getattr(self, "_cached_stream_info", None), dict):
            self._cached_stream_info = {}
        self._cached_stream_info[stream] = dict(updated)
        if self.data is not None:
            media_profiles = {
                key: {name: dict(value) for name, value in profile.items()}
                for key, profile in self.data.media_profiles.items()
            }
            media_profiles.setdefault(stream, {})["stream"] = dict(updated)
            stream_info = dict(updated) if stream == "sub" else self.data.stream_info
            self.async_set_updated_data(
                replace(
                    self.data,
                    media_profiles=media_profiles,
                    stream_info=stream_info,
                )
            )
        if enabled and isinstance(self.client, RecameraDeviceClient):
            await self._async_wait_rtsp_ready(stream)
        return updated

    async def _async_wait_rtsp_ready(self, stream: str, timeout: float = 4.0) -> None:
        """Wait briefly for the device RTSP server to accept connections."""
        source_url = self.get_stream_url(stream)
        if not source_url:
            return
        parsed = urlsplit(source_url)
        host = parsed.hostname
        if not host:
            return
        port = parsed.port or 554
        path = parsed.path or f"/{stream}"
        probe_uri = f"rtsp://{host}:{port}{path}"
        request = (
            f"OPTIONS {probe_uri} RTSP/1.0\r\n"
            f"CSeq: 1\r\n"
            f"User-Agent: HomeAssistant-reCamera-Pro\r\n\r\n"
        ).encode("ascii")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self._stop.is_set():
            writer: asyncio.StreamWriter | None = None
            try:
                reader, opened_writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=0.5,
                )
                writer = opened_writer
                opened_writer.write(request)
                await asyncio.wait_for(opened_writer.drain(), timeout=0.5)
                line = await asyncio.wait_for(reader.readline(), timeout=0.5)
                if line.startswith(b"RTSP/1."):
                    return
            except OSError, TimeoutError:
                pass
            finally:
                if writer is not None:
                    writer.close()
                    with contextlib.suppress(OSError, TimeoutError):
                        await asyncio.wait_for(writer.wait_closed(), timeout=0.2)
            await asyncio.sleep(0.25)

    def get_stream_url(self, stream: str = "sub") -> str | None:
        """Return the external RTSP URL with the current device host."""
        if self.data is None:
            return None
        profile = self.data.media_profiles.get(stream) or {}
        stream_info = profile.get("stream") or {}
        if not stream_info and stream == "sub":
            stream_info = self.data.stream_info
        rtsp = stream_info.get("rtsp") or {}
        source_url = str(rtsp.get("sURL") or "")
        if not source_url or rtsp.get("iEnabled") != 1:
            return None
        try:
            parsed = urlsplit(source_url)
            port = parsed.port or 554
        except ValueError:
            _LOGGER.debug("Ignoring malformed RTSP URL from reCamera")
            return None
        username = parsed.username
        password = parsed.password
        auth = ""
        if username:
            auth = quote(username, safe="")
            if password is not None:
                auth += f":{quote(password, safe='')}"
            auth += "@"
        netloc = f"{auth}{format_url_host(self.config_entry.data[CONF_HOST])}:{port}"
        if stream == "main":
            path = "/main"
        elif stream == "sub":
            path = "/sub"
        else:
            path = parsed.path
        return urlunsplit((parsed.scheme or "rtsp", netloc, path, parsed.query, ""))

    def _start_reauth(self) -> None:
        """Start one reauth flow for invalid credentials."""
        if self._reauth_started:
            return
        self._reauth_started = True
        self.config_entry.async_start_reauth(self.hass)

    def _async_save_store(self, catalog: dict[str, DetectedClass]) -> None:
        """Persist builtin YOLO class metadata."""
        if self._stop.is_set():
            return
        self._store.async_delay_save(
            lambda: self._store_payload(catalog),
            30,
        )

    def _store_payload(
        self,
        catalog: dict[str, DetectedClass] | None = None,
    ) -> dict[str, Any]:
        """Return the persistent coordinator payload."""
        catalog = (
            catalog
            if catalog is not None
            else (self.data.class_catalog if self.data is not None else {})
        )
        payload: dict[str, Any] = {
            "class_catalog": [
                item.as_dict()
                for item in sorted(
                    catalog.values(),
                    key=lambda detected: detected.key,
                )
            ]
        }
        if self._cached_stream_info:
            payload["media_streams"] = {
                stream: dict(value)
                for stream, value in self._cached_stream_info.items()
            }
        if self._firmware_reboot is not None:
            payload["firmware_reboot"] = dict(self._firmware_reboot)
        return payload

    async def _sleep(self, delay: float) -> None:
        """Sleep while allowing a prompt shutdown."""
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
        except TimeoutError:
            return

    async def _close_websocket(self) -> None:
        """Close the current websocket without ending the coordinator."""
        websocket, self._websocket = self._websocket, None
        if websocket is not None and not websocket.closed:
            try:
                await asyncio.wait_for(websocket.close(), timeout=1.0)
            except TimeoutError:
                _LOGGER.debug("Timed out waiting for reCamera websocket close")

    @override
    async def async_shutdown(self) -> None:
        """Stop background tasks and release the API session."""
        if self._unsub_stop is not None:
            self._unsub_stop()
            self._unsub_stop = None
        self._stop.set()
        for task in (
            getattr(self, "_websocket_task", None),
            getattr(self, "_connection_recovery_task", None),
            getattr(self, "_firmware_check_task", None),
            getattr(self, "_stale_task", None),
            getattr(self, "_firmware_reboot_task", None),
        ):
            if task is None:
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._websocket_task = None
        self._connection_recovery_task = None
        self._firmware_check_task = None
        self._stale_task = None
        self._firmware_reboot_task = None
        await self.capture_controller.async_shutdown()
        _cancel_pending_store_save(getattr(self, "_store", None))
        await self._close_websocket()
        await self.client.async_close()
        self._client_session = None


def _cancel_pending_store_save(store: Any) -> None:
    """Cancel any pending delayed/final write listeners on a HA Store."""
    if store is None:
        return
    for method_name in (
        "_async_cleanup_delay_listener",
        "_async_cleanup_final_write_listener",
    ):
        cleanup = getattr(store, method_name, None)
        if callable(cleanup):
            cleanup()


async def async_remove_store(hass: HomeAssistant, entry_id: str) -> None:
    """Remove persisted YOLO class metadata."""
    await Store[dict[str, Any]](
        hass,
        STORAGE_VERSION,
        f"{DOMAIN}.{entry_id}",
    ).async_remove()

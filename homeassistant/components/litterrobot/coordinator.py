"""The Litter-Robot coordinator."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any

from pylitterbot import Account, FeederRobot, LitterRobot, LitterRobot5
from pylitterbot.enums import LitterBoxStatus
from pylitterbot.event import EVENT_UPDATE
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_RECORDING_DURATION,
    CONF_RECORDING_ENABLED,
    CONF_RECORDING_EVENT_TYPES,
    CONF_RECORDING_RETENTION,
    DEFAULT_RECORDING_DURATION,
    DEFAULT_RECORDING_EVENT_TYPES,
    DEFAULT_RECORDING_RETENTION_DAYS,
    DOMAIN,
)
from .recording import RecordingManager

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)
CAMERA_POLL_INTERVAL = timedelta(seconds=10)
CAMERA_STATE_POLL_INTERVAL = timedelta(seconds=3)
CLEANUP_INTERVAL = timedelta(hours=6)

_CAMEL_TO_SNAKE: dict[str, str] = {
    "petVisit": "pet_visit",
    "catDetect": "cat_detect",
    "cat_detected": "cat_detect",
    "cycleCompleted": "cycle_completed",
    "cycleInterrupted": "cycle_interrupted",
    "motion": "motion",
    "litterLow": "litter_low",
    "offline": "offline",
}


def _normalize_event_type(raw: str) -> str:
    """Convert Whisker API event type to lowercase snake_case."""
    if raw in _CAMEL_TO_SNAKE:
        return _CAMEL_TO_SNAKE[raw]
    return raw.lower().replace(" ", "_")


type LitterRobotConfigEntry = ConfigEntry[LitterRobotDataUpdateCoordinator]


class LitterRobotDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """The Litter-Robot data update coordinator."""

    config_entry: LitterRobotConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: LitterRobotConfigEntry
    ) -> None:
        """Initialize the Litter-Robot data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.account = Account(websession=async_get_clientsession(hass))
        self.camera_activities: dict[str, list[dict[str, Any]]] = {}
        self.camera_thumbnails: dict[str, bytes] = {}
        self.recording_maps: dict[str, dict[str, str]] = {}

        self.recording_manager: RecordingManager | None = None
        self._recording_event_types: list[str] = []
        self._last_activity_ids: dict[str, str] = {}
        self._last_video_ids: dict[str, str] = {}
        self._last_robot_status: dict[str, LitterBoxStatus] = {}
        self._cancel_camera_poll: Callable[[], None] | None = None
        self._cancel_state_poll: Callable[[], None] | None = None
        self._cancel_cleanup: Callable[[], None] | None = None
        self._unsub_robot_updates: list[Callable[[], None]] = []
        self._first_poll_done: bool = False

    @property
    def pet_name_map(self) -> dict[str, str]:
        """Return a mapping of pet ID to pet name."""
        return {pet.id: pet.name for pet in self.account.pets}

    async def _async_update_data(self) -> None:
        """Update all device states from the Litter-Robot API."""
        try:
            await self.account.refresh_robots()
            await self.account.load_pets()
            for pet in self.account.pets:
                # Need to fetch weight history for `get_visits_since`
                await pet.fetch_weight_history()
            for robot in self.account.robots:
                if isinstance(robot, LitterRobot5) and robot.has_camera:
                    await self._async_fetch_camera_data(robot)
        except LitterRobotLoginException as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_credentials"
            ) from ex
        except LitterRobotException as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(ex)},
            ) from ex

    async def _async_fetch_camera_data(self, robot: LitterRobot5) -> None:
        """Fetch recent activities and latest video thumbnail for a camera robot."""
        try:
            if not self._first_poll_done:
                # First poll: warm-up unlocks the full API response buffer
                await robot.get_activities()
                # Fetch up to 100 pet visits for daily aggregates
                visits = await robot.get_activities(
                    limit=100, offset=0, activity_type="PET_VISIT"
                )
                # Fetch recent of all types for last event sensor
                recent = await robot.get_activities(limit=5, offset=0)
            else:
                # Subsequent polls: API only returns new/unread activities
                recent = await robot.get_activities(limit=10)
                visits = []

            # Merge new activities into the existing cache
            existing = self.camera_activities.get(robot.serial, [])
            seen = {a.get("messageId") for a in existing if a.get("messageId")}
            merged = list(existing)
            for a in list(recent) + list(visits):
                mid = a.get("messageId")
                if mid and mid not in seen:
                    merged.append(a)
                    seen.add(mid)
            # Sort newest first
            merged.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
            activities = merged
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Failed to fetch activities for %s", robot.name, exc_info=True
            )
            activities = self.camera_activities.get(robot.serial, [])
        self.camera_activities[robot.serial] = activities
        if not self._first_poll_done:
            self._first_poll_done = True
            _LOGGER.debug(
                "Initial activity cache for %s: %d total", robot.name, len(activities)
            )

        try:
            videos = await robot.get_camera_videos(limit=1)
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Failed to fetch camera videos for %s", robot.name, exc_info=True
            )
            return

        if not videos:
            return

        thumbnail_url = videos[0].thumbnail_url
        if not thumbnail_url:
            return

        try:
            session = async_get_clientsession(self.hass)
            resp = await session.get(thumbnail_url)
            if resp.status == 200:
                self.camera_thumbnails[robot.serial] = await resp.read()
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Failed to download thumbnail for %s", robot.name, exc_info=True
            )

        # Refresh recording map (filesystem I/O, run in executor)
        self.recording_maps[robot.serial] = await self.hass.async_add_executor_job(
            self._build_recording_map, robot.serial
        )

    def _build_recording_map(self, serial: str) -> dict[str, str]:
        """Build filename -> player URL map for recordings (runs in executor)."""
        media_dir = Path(self.hass.config.path("media")) / "litterrobot" / serial
        if not media_dir.is_dir():
            return {}
        try:
            return {
                fp.name: f"/api/litterrobot/player/{serial}/{fp.name}"
                for fp in media_dir.iterdir()
                if fp.suffix == ".mp4"
            }
        except OSError:
            return {}

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.account.connect(
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                load_robots=True,
                subscribe_for_updates=True,
                load_pets=True,
            )
        except LitterRobotLoginException as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_credentials"
            ) from ex
        except LitterRobotException as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(ex)},
            ) from ex

        self._setup_recording()

    def _setup_recording(self) -> None:
        """Set up the recording manager if enabled in options."""
        if not self.config_entry.options.get(CONF_RECORDING_ENABLED, False):
            return

        media_dir = Path(self.hass.config.path("media")) / "litterrobot"
        duration = self.config_entry.options.get(
            CONF_RECORDING_DURATION, DEFAULT_RECORDING_DURATION
        )
        retention_days = self.config_entry.options.get(
            CONF_RECORDING_RETENTION, DEFAULT_RECORDING_RETENTION_DAYS
        )

        self._recording_event_types = self.config_entry.options.get(
            CONF_RECORDING_EVENT_TYPES, DEFAULT_RECORDING_EVENT_TYPES
        )

        self.recording_manager = RecordingManager(
            hass=self.hass,
            media_dir=media_dir,
            duration=duration,
            retention_days=retention_days,
        )

        # Subscribe to WebSocket state updates for immediate cycle/visit detection.
        # The EVENT_UPDATE callback fires synchronously when the robot's state changes
        # via the WebSocket push, eliminating the poll-interval + REST-call latency
        # (~15 s) that would otherwise delay cycle recording start.
        for robot in self.account.robots:
            if isinstance(robot, LitterRobot5) and robot.has_camera:
                self._unsub_robot_updates.append(
                    robot.on(EVENT_UPDATE, lambda r=robot: self._on_robot_update(r))
                )

        self._cancel_camera_poll = async_track_time_interval(
            self.hass,
            self._async_fast_camera_poll,
            CAMERA_POLL_INTERVAL,
            name="litterrobot_camera_poll",
        )

        # Faster state-only poll for low-latency cycle start detection.
        # LR5 has no WebSocket push; the only way to detect CLEAN_CYCLE is REST
        # polling. At 3 s + ~2-5 s API call, cycle recording starts within ~8 s
        # of the actual cycle start rather than the ~15 s from the 10-second poll.
        self._cancel_state_poll = async_track_time_interval(
            self.hass,
            self._async_fast_state_poll,
            CAMERA_STATE_POLL_INTERVAL,
            name="litterrobot_state_poll",
        )

        self._cancel_cleanup = async_track_time_interval(
            self.hass,
            self._async_periodic_cleanup,
            CLEANUP_INTERVAL,
            name="litterrobot_recording_cleanup",
        )

        _LOGGER.info(
            "Recording enabled: duration=%ds, retention=%dd",
            duration,
            retention_days,
        )

    async def _async_fast_camera_poll(self, _now: datetime) -> None:
        """Poll camera activities and videos every 10 seconds."""
        if self.recording_manager is None:
            return

        for robot in self.account.robots:
            if not isinstance(robot, LitterRobot5) or not robot.has_camera:
                continue

            # Activity and video checks run independently so a failure in
            # one doesn't skip the other.
            await self._async_poll_activities(robot)
            await self._async_poll_camera_videos(robot)

    async def _async_fast_state_poll(self, _now: datetime) -> None:
        """Poll robot state every 3 seconds for low-latency cycle detection."""
        if self.recording_manager is None:
            return

        for robot in self.account.robots:
            if not isinstance(robot, LitterRobot5) or not robot.has_camera:
                continue

            await self._async_check_robot_state(robot)

    async def _async_poll_activities(self, robot: LitterRobot5) -> None:
        """Poll activities API and trigger recording on new events."""
        assert self.recording_manager is not None

        try:
            activities = await robot.get_activities(limit=3)
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Fast poll: failed to fetch activities for %s",
                robot.name,
                exc_info=True,
            )
            return

        if not activities:
            return

        latest = activities[0]
        activity_id = str(
            latest.get("messageId", latest.get("activityId", latest.get("id", "")))
        )

        if not activity_id:
            return

        prev_id = self._last_activity_ids.get(robot.serial)
        self._last_activity_ids[robot.serial] = activity_id

        # Skip first poll to avoid recording stale events at startup
        if prev_id is None:
            return

        if activity_id == prev_id:
            return

        # Normalize event type and check against configured types
        raw_type = str(latest.get("eventType", latest.get("type", "")))
        event_type = _normalize_event_type(raw_type)

        if event_type not in self._recording_event_types:
            _LOGGER.debug(
                "Skipping %s event for %s (not in configured types)",
                event_type,
                robot.name,
            )
            return

        _LOGGER.debug(
            "New activity for %s: %s type=%s (prev: %s)",
            robot.name,
            activity_id,
            event_type,
            prev_id,
        )

        if event_type == "cat_detect":
            # Start continuous visit recording (front → globe)
            self.recording_manager.trigger_visit_recording(robot)

        elif event_type == "pet_visit":
            pet_id, pet_name = self._resolve_pet(latest)
            # Signal active visit recording if one exists
            signaled = self.recording_manager.signal_visit_complete(
                robot.serial,
                pet_name=pet_name,
                pet_id=pet_id,
            )
            if not signaled:
                # No active visit — do a standalone fixed recording
                self.recording_manager.trigger_recording(
                    robot,
                    latest,
                    pet_name_map=self.pet_name_map,
                    camera_view="globe",
                )

        elif event_type in (
            "cycle_completed",
            "cycle_interrupted",
        ):
            # Signal active cycle recording if one exists; otherwise
            # fall back to a fixed recording (e.g. cycle started before
            # recording was enabled)
            if not self.recording_manager.signal_cycle_complete(robot.serial):
                self.recording_manager.trigger_recording(
                    robot,
                    latest,
                    pet_name_map=self.pet_name_map,
                    camera_view="globe",
                )

        else:
            # Other configured event types — fixed recording, no view change
            self.recording_manager.trigger_recording(
                robot, latest, pet_name_map=self.pet_name_map
            )

    async def _async_poll_camera_videos(self, robot: LitterRobot5) -> None:
        """Poll camera videos endpoint for cat_detected events."""
        assert self.recording_manager is not None

        try:
            videos = await robot.get_camera_videos(limit=3)
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Fast poll: failed to fetch camera videos for %s",
                robot.name,
                exc_info=True,
            )
            return

        if not videos:
            return

        latest_video = videos[0]
        video_id = latest_video.id

        if not video_id:
            return

        prev_id = self._last_video_ids.get(robot.serial)
        self._last_video_ids[robot.serial] = video_id

        # Skip first poll to avoid triggering on stale videos at startup
        if prev_id is None:
            return

        if video_id != prev_id:
            event_type = _normalize_event_type(latest_video.event_type or "")

            if event_type != "cat_detect":
                return

            if event_type not in self._recording_event_types:
                _LOGGER.debug(
                    "Skipping %s video event for %s (not in configured types)",
                    event_type,
                    robot.name,
                )
                return

            _LOGGER.debug(
                "New camera video for %s: %s type=%s (prev: %s)",
                robot.name,
                video_id,
                event_type,
                prev_id,
            )
            self.recording_manager.trigger_visit_recording(robot)

    async def _async_check_robot_state(self, robot: LitterRobot5) -> None:
        """Detect robot state transitions and trigger recordings."""
        assert self.recording_manager is not None

        try:
            await robot.refresh()
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Fast poll: failed to refresh state for %s",
                robot.name,
                exc_info=True,
            )
            return

        current_status = robot.status
        prev_status = self._last_robot_status.get(robot.serial)
        self._last_robot_status[robot.serial] = current_status

        # Skip first poll to establish baseline
        if prev_status is None:
            return

        if current_status == prev_status:
            return

        _LOGGER.debug(
            "State transition for %s: %s -> %s",
            robot.name,
            prev_status.text,
            current_status.text,
        )

        if (
            current_status == LitterBoxStatus.CLEAN_CYCLE
            and "cycle_completed" in self._recording_event_types
        ):
            _LOGGER.debug(
                "Cycling started for %s, triggering cycle recording on globe",
                robot.name,
            )
            self.recording_manager.trigger_cycle_recording(robot)

        elif (
            prev_status == LitterBoxStatus.CLEAN_CYCLE
            and current_status != LitterBoxStatus.CLEAN_CYCLE
        ):
            # Cycle ended — signal active cycle recording to stop
            self.recording_manager.signal_cycle_complete(robot.serial)

        elif (
            current_status == LitterBoxStatus.CAT_DETECTED
            and "cat_detect" in self._recording_event_types
        ):
            _LOGGER.debug(
                "Cat detected via robot state for %s, triggering visit recording",
                robot.name,
            )
            self.recording_manager.trigger_visit_recording(robot)

    def _on_robot_update(self, robot: LitterRobot5) -> None:
        """Handle a WebSocket state update for immediate recording triggers.

        Called synchronously by pylitterbot's event system whenever the robot's
        state changes via WebSocket push. Fires before the 10-second poll timer,
        so cycle/visit recordings start as soon as the state change arrives.
        """
        if self.recording_manager is None:
            return

        current_status = robot.status
        prev_status = self._last_robot_status.get(robot.serial)
        self._last_robot_status[robot.serial] = current_status

        if prev_status is None or current_status == prev_status:
            return

        _LOGGER.debug(
            "WS state change for %s: %s -> %s",
            robot.name,
            prev_status.text,
            current_status.text,
        )

        if (
            current_status == LitterBoxStatus.CLEAN_CYCLE
            and "cycle_completed" in self._recording_event_types
        ):
            _LOGGER.debug(
                "Cycle started for %s (WS), triggering cycle recording", robot.name
            )
            self.recording_manager.trigger_cycle_recording(robot)

        elif (
            prev_status == LitterBoxStatus.CLEAN_CYCLE
            and current_status != LitterBoxStatus.CLEAN_CYCLE
        ):
            self.recording_manager.signal_cycle_complete(robot.serial)

        elif (
            current_status == LitterBoxStatus.CAT_DETECTED
            and "cat_detect" in self._recording_event_types
        ):
            _LOGGER.debug(
                "Cat detected for %s (WS), triggering visit recording", robot.name
            )
            self.recording_manager.trigger_visit_recording(robot)

    def _resolve_pet(self, activity: dict[str, Any]) -> tuple[str | None, str]:
        """Resolve pet ID and name from an activity dict."""
        raw = activity.get("petId") or (activity.get("petIds") or [None])[0]
        if raw:
            pet_id = str(raw)
            return pet_id, self.pet_name_map.get(pet_id, "unknown")
        return None, "unknown"

    async def _async_periodic_cleanup(self, _now: datetime) -> None:
        """Run periodic recording cleanup."""
        if self.recording_manager is not None:
            await self.recording_manager.async_cleanup_old_recordings()

    async def async_shutdown(self) -> None:
        """Shut down recording manager and cancel timers."""
        for unsub in self._unsub_robot_updates:
            unsub()
        self._unsub_robot_updates.clear()

        if self._cancel_camera_poll is not None:
            self._cancel_camera_poll()
            self._cancel_camera_poll = None

        if self._cancel_state_poll is not None:
            self._cancel_state_poll()
            self._cancel_state_poll = None

        if self._cancel_cleanup is not None:
            self._cancel_cleanup()
            self._cancel_cleanup = None

        if self.recording_manager is not None:
            await self.recording_manager.async_stop()
            self.recording_manager = None

    def get_recording_map(self, serial: str) -> dict[str, str]:
        """Return the cached filename -> URL map for recordings of this robot."""
        return self.recording_maps.get(serial, {})

    def rename_recording_for_reassign(
        self,
        serial: str,
        activity: dict[str, Any],
        new_pet_name: str | None,
    ) -> None:
        """Rename the recording file to reflect a pet reassignment.

        Searches for a recording matching the activity's timestamp and renames
        it with the new pet name (or removes the pet name for unassign).
        """
        media_dir = Path(self.hass.config.path("media")) / "litterrobot" / serial
        if not media_dir.is_dir():
            return

        timestamp = activity.get("timestamp")
        if not timestamp:
            return

        # Parse timestamp to match filename format: YYYYMMDD_HHMMSS
        try:
            activity_dt = datetime.fromisoformat(timestamp)
            file_prefix = activity_dt.strftime("%Y%m%d_%H%M")
        except ValueError, TypeError:
            return

        # Find recordings matching this timestamp (within the same minute)
        for filepath in media_dir.iterdir():
            if not filepath.name.startswith(file_prefix):
                continue
            if filepath.suffix != ".mp4":
                continue

            old_name = filepath.name
            # Strip existing pet name: split on _VISIT_ or _PET_VISIT_
            # Patterns: YYYYMMDD_HHMMSS_VISIT_PetName.mp4
            #           YYYYMMDD_HHMMSS_PET_VISIT_PetName.mp4
            #           YYYYMMDD_HHMMSS_VISIT.mp4
            for marker in ("_PET_VISIT_", "_VISIT_", "_PET_VISIT.", "_VISIT."):
                if marker in old_name:
                    base = old_name.split(marker)[0]
                    if new_pet_name:
                        suffix = marker.rstrip(".").rstrip("_")
                        new_name = f"{base}{suffix}_{new_pet_name}.mp4"
                    else:
                        suffix = marker.rstrip(".").rstrip("_")
                        new_name = f"{base}{suffix}.mp4"
                    new_path = filepath.with_name(new_name)
                    if new_path != filepath:
                        filepath.rename(new_path)
                        _LOGGER.debug("Renamed recording: %s -> %s", old_name, new_name)
                    break

    def litter_robots(self) -> Generator[LitterRobot]:
        """Get Litter-Robots from the account."""
        return (
            robot for robot in self.account.robots if isinstance(robot, LitterRobot)
        )

    def feeder_robots(self) -> Generator[FeederRobot]:
        """Get Feeder-Robots from the account."""
        return (
            robot for robot in self.account.robots if isinstance(robot, FeederRobot)
        )

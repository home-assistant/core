"""Automatic updates of Home Assistant Core patch releases."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
import logging
import random
from typing import Any, Self, TypedDict, override

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import ContextType, IssueType, Job, UpdateChannel
from awesomeversion import AwesomeVersion
import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_NAME,
    EVENT_LOGBOOK_ENTRY,
    WEEKDAYS,
    __version__ as HA_VERSION,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .config_entry import async_get_update_options
from .const import (
    CORE_AUTO_UPDATE_DELAYS,
    DEFAULT_CORE_AUTO_UPDATE_DELAY,
    DEFAULT_CORE_AUTO_UPDATE_WINDOW_END,
    DEFAULT_CORE_AUTO_UPDATE_WINDOW_START,
    DOMAIN,
    JOBS_COORDINATOR,
    OPTION_CORE_AUTO_UPDATE,
    OPTION_CORE_AUTO_UPDATE_DELAY,
    OPTION_CORE_AUTO_UPDATE_WEEKDAYS,
    OPTION_CORE_AUTO_UPDATE_WINDOW_END,
    OPTION_CORE_AUTO_UPDATE_WINDOW_START,
    OPTION_CORE_BACKUP_BEFORE_UPDATE,
)
from .coordinator import HassioMainDataUpdateCoordinator, JobSubscription
from .handler import get_supervisor_client
from .update_helper import update_core

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "hassio.auto_update"
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 4

CHECK_INTERVAL = timedelta(minutes=5)
# Long enough that a check always lands inside the window
MIN_WINDOW_LENGTH = timedelta(minutes=30)

HISTORY_LENGTH = 10

ISSUE_ROLLED_BACK = "core_auto_update_rolled_back"
ISSUE_FAILED = "core_auto_update_failed"

# Supervisor jobs that must finish before Home Assistant is updated
_BUSY_JOB_NAME = "home_assistant_core_update"
_BUSY_JOB_PREFIX = "backup_manager_"

# Options are stored as text, so store times the way the settings read them
_time_string = probatio.All(cv.time, time.isoformat)


def _window_length(start: time, end: time) -> timedelta:
    """Return how long a time window is; it may cross midnight."""
    length = datetime.combine(date.min, end) - datetime.combine(date.min, start)
    return length % timedelta(days=1)


def _validate_window(options: dict[str, Any]) -> dict[str, Any]:
    """Reject a too short time window; one that crosses midnight is fine."""
    start = time.fromisoformat(
        options.get(
            OPTION_CORE_AUTO_UPDATE_WINDOW_START, DEFAULT_CORE_AUTO_UPDATE_WINDOW_START
        )
    )
    end = time.fromisoformat(
        options.get(
            OPTION_CORE_AUTO_UPDATE_WINDOW_END, DEFAULT_CORE_AUTO_UPDATE_WINDOW_END
        )
    )
    if _window_length(start, end) < MIN_WINDOW_LENGTH:
        raise probatio.Invalid("The time window must be at least 30 minutes long")
    return options


AUTO_UPDATE_OPTIONS_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Optional(OPTION_CORE_AUTO_UPDATE): bool,
            probatio.Optional(OPTION_CORE_AUTO_UPDATE_DELAY): probatio.In(
                CORE_AUTO_UPDATE_DELAYS
            ),
            probatio.Optional(OPTION_CORE_AUTO_UPDATE_WINDOW_START): _time_string,
            probatio.Optional(OPTION_CORE_AUTO_UPDATE_WINDOW_END): _time_string,
            probatio.Optional(OPTION_CORE_AUTO_UPDATE_WEEKDAYS): probatio.All(
                cv.weekdays, probatio.Length(min=1)
            ),
        },
        extra=probatio.ALLOW_EXTRA,
    ),
    _validate_window,
)


class AutoUpdateUnavailableReason(StrEnum):
    """Why automatic updates are not available on this installation."""

    NOT_HOME_ASSISTANT_OS = "not_home_assistant_os"
    NOT_STABLE_CHANNEL = "not_stable_channel"


@dataclass(frozen=True, kw_only=True)
class AutoUpdateSettings:
    """The user's settings for automatic Home Assistant updates."""

    # None means the user has not made a choice yet
    enabled: bool | None
    delay: timedelta
    window_start: time
    window_end: time
    weekdays: frozenset[str]

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> Self:
        """Build the settings from the hassio config entry options."""
        return cls(
            enabled=options.get(OPTION_CORE_AUTO_UPDATE),
            delay=timedelta(
                days=options.get(
                    OPTION_CORE_AUTO_UPDATE_DELAY, DEFAULT_CORE_AUTO_UPDATE_DELAY
                )
            ),
            window_start=time.fromisoformat(
                options.get(
                    OPTION_CORE_AUTO_UPDATE_WINDOW_START,
                    DEFAULT_CORE_AUTO_UPDATE_WINDOW_START,
                )
            ),
            window_end=time.fromisoformat(
                options.get(
                    OPTION_CORE_AUTO_UPDATE_WINDOW_END,
                    DEFAULT_CORE_AUTO_UPDATE_WINDOW_END,
                )
            ),
            weekdays=frozenset(options.get(OPTION_CORE_AUTO_UPDATE_WEEKDAYS, WEEKDAYS)),
        )


class AutoUpdateResult(StrEnum):
    """How an automatic update ended."""

    SUCCESS = "success"
    # Supervisor installed it, but the health check failed and it rolled back
    ROLLED_BACK = "rolled_back"
    # The update did not start, like a backup or Supervisor error
    FAILED = "failed"


class PendingUpdate(TypedDict):
    """An automatic update that Home Assistant restarts in the middle of."""

    from_version: str
    to_version: str
    started: str


class AutoUpdateHistoryEntry(PendingUpdate):
    """A finished automatic update."""

    finished: str
    result: AutoUpdateResult


class AutoUpdateStoreData(TypedDict):
    """Stored data for automatic Home Assistant updates."""

    first_seen: dict[str, str]
    skipped: list[str]
    window_offset: float
    attempted_window: str | None
    pending: PendingUpdate | None
    history: list[AutoUpdateHistoryEntry]


class _AutoUpdateStore(Store[AutoUpdateStoreData]):
    """Store for automatic Home Assistant updates."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        super().__init__(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        )

    @override
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_minor_version < 2:
            # Version 1.2 adds the versions skipped for automatic updates
            old_data["skipped"] = []
        if old_minor_version < 3:
            # Version 1.3 adds where in the time window this installation
            # updates, and the window it last tried to update in
            old_data["window_offset"] = random.random()
            old_data["attempted_window"] = None
        if old_minor_version < 4:
            # Version 1.4 adds the update in progress and the past updates
            old_data["pending"] = None
            old_data["history"] = []
        return old_data


def _window_start(settings: AutoUpdateSettings, now: datetime) -> datetime | None:
    """Return when the time window that now falls in started, if any.

    A window that crosses midnight belongs to the day it starts on, so its
    weekday decides whether it is allowed.
    """
    length = _window_length(settings.window_start, settings.window_end)
    for days_back in (0, 1):
        start = datetime.combine(
            now.date() - timedelta(days=days_back),
            settings.window_start,
            tzinfo=now.tzinfo,
        )
        if start <= now < start + length:
            if WEEKDAYS[start.weekday()] in settings.weekdays:
                return start
            return None
    return None


def _major(version: str) -> tuple[int, int]:
    """Return the major release of a version, like (2026, 10) for 2026.10.2."""
    parsed = AwesomeVersion(version)
    return (int(parsed.section(0)), int(parsed.section(1)))


class AutoUpdateManager:
    """Keep the state for automatic Home Assistant updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: HassioMainDataUpdateCoordinator,
    ) -> None:
        """Initialize the manager."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._store = _AutoUpdateStore(hass)
        self._first_seen: dict[str, datetime] = {}
        self._skipped: set[str] = set()
        self._window_offset = random.random()
        self._attempted_window: datetime | None = None
        self._pending: PendingUpdate | None = None
        # The pending update as found at setup, which Home Assistant restarted in
        self._restored_pending: PendingUpdate | None = None
        self._unsub_settling: CALLBACK_TYPE | None = None
        self._history: list[AutoUpdateHistoryEntry] = []

    async def async_setup(self) -> None:
        """Load the stored data and start tracking offered versions."""
        if (data := await self._store.async_load()) is not None:
            self._first_seen = {
                version: datetime.fromisoformat(first_seen)
                for version, first_seen in data["first_seen"].items()
            }
            self._skipped = set(data["skipped"])
            self._window_offset = data["window_offset"]
            if (attempted_window := data["attempted_window"]) is not None:
                self._attempted_window = datetime.fromisoformat(attempted_window)
            self._pending = data["pending"]
            self._history = data["history"]
        else:
            self._async_save()

        # Settled once started: Supervisor rolls back a version that does not
        # come up, and that has to find the record still there.
        if self._pending is not None:
            self._restored_pending = self._pending
            self._entry.async_on_unload(
                async_at_started(self._hass, self._async_start_settling)
            )

        self._async_record_offered_version()
        self._entry.async_on_unload(
            self._coordinator.async_add_listener(self._async_record_offered_version)
        )
        self._entry.async_on_unload(
            async_at_started(self._hass, self._async_start_checking)
        )

    @callback
    def _async_start_checking(self, hass: HomeAssistant) -> None:
        """Check now and on an interval, once Home Assistant has started."""
        self._entry.async_on_unload(
            async_track_time_interval(
                hass,
                self._async_schedule_check,
                CHECK_INTERVAL,
                cancel_on_shutdown=True,
            )
        )
        self._async_schedule_check()

    @callback
    def _async_schedule_check(self, _now: datetime | None = None) -> None:
        """Run a check as a background task, so unloading cancels it."""
        self._entry.async_create_background_task(
            self._hass, self._async_check(), "hassio automatic update check"
        )

    @callback
    def _async_start_settling(self, hass: HomeAssistant) -> None:
        """Settle the restored update now, or once Supervisor is done with it.

        Supervisor can still be busy with it, like after a reload of this
        integration during the update.
        """
        self._unsub_settling = hass.data[JOBS_COORDINATOR].subscribe(
            JobSubscription(self._async_core_update_job_changed, name=_BUSY_JOB_NAME)
        )
        self._entry.async_on_unload(self._async_stop_settling)
        if not self._async_core_update_running():
            self._async_schedule_settle()

    @callback
    def _async_core_update_running(self) -> bool:
        """Return if Supervisor is updating Home Assistant Core."""
        return any(
            job.name == _BUSY_JOB_NAME and job.done is False
            for job in self._hass.data[JOBS_COORDINATOR].current_jobs
        )

    @callback
    def _async_core_update_job_changed(self, job: Job) -> None:
        """Settle the restored update once Supervisor finished it."""
        if job.done:
            self._async_schedule_settle()

    @callback
    def _async_schedule_settle(self) -> None:
        """Settle the restored update as a background task."""
        self._entry.async_create_background_task(
            self._hass, self._async_settle(), "hassio automatic update result"
        )

    @callback
    def _async_stop_settling(self) -> None:
        """Stop watching Supervisor for the restored update."""
        self._restored_pending = None
        if self._unsub_settling is not None:
            self._unsub_settling()
            self._unsub_settling = None

    async def _async_supervisor_rolled_back(self) -> bool | None:
        """Return if Supervisor rolled Core back, or None if it cannot tell now.

        Asked directly; hassio's own issue list can be empty after a failed
        refresh, or miss an issue whose suggestions could not be loaded.
        """
        try:
            info = await get_supervisor_client(self._hass).resolution.info()
        except SupervisorError as err:
            _LOGGER.debug("Could not ask Supervisor about a rollback: %s", err)
            return None

        return any(
            issue.type == IssueType.UPDATE_ROLLBACK
            and issue.context == ContextType.CORE
            for issue in info.issues
        )

    async def _async_settle(self) -> None:
        """Find out how the update restored from the record went.

        Supervisor checks the new version and rolls back when it does not
        come up healthy, and says so. Still running the old version without
        that means the update never happened. When Supervisor cannot tell
        yet, the record stays and the next check asks again.
        """
        if (pending := self._restored_pending) is None or self._pending is not pending:
            return

        hass = self._hass
        to_version = pending["to_version"]
        if to_version == HA_VERSION:
            self._pending = None
            self._async_add_history(pending, AutoUpdateResult.SUCCESS)
            async_delete_issue(hass, DOMAIN, ISSUE_FAILED)
            hass.bus.async_fire(
                EVENT_LOGBOOK_ENTRY,
                {
                    ATTR_NAME: "Home Assistant",
                    "message": (
                        f"was updated automatically from "
                        f"{pending['from_version']} to {to_version}"
                    ),
                    ATTR_DOMAIN: DOMAIN,
                },
            )
        elif pending["from_version"] == HA_VERSION:
            rolled_back = await self._async_supervisor_rolled_back()
            # Settled meanwhile, or Supervisor cannot tell yet
            if self._pending is not pending or rolled_back is None:
                return

            if not rolled_back:
                self._async_stop_settling()
                self._async_update_failed(to_version)
                return

            # Never try this version again on our own
            self._pending = None
            self._skipped.add(to_version)
            self._async_add_history(pending, AutoUpdateResult.ROLLED_BACK)
            async_delete_issue(hass, DOMAIN, ISSUE_FAILED)
            async_create_issue(
                hass,
                DOMAIN,
                ISSUE_ROLLED_BACK,
                is_fixable=False,
                is_persistent=True,
                severity=IssueSeverity.ERROR,
                translation_key=ISSUE_ROLLED_BACK,
                translation_placeholders={"version": to_version},
            )
        else:
            # Someone else changed the version; nothing to tell
            self._pending = None

        self._async_stop_settling()
        self._async_save()

    @callback
    def _async_add_history(
        self, pending: PendingUpdate, result: AutoUpdateResult
    ) -> None:
        """Remember how an automatic update ended."""
        self._history = [
            *self._history,
            AutoUpdateHistoryEntry(
                **pending,
                finished=dt_util.utcnow().isoformat(),
                result=result,
            ),
        ][-HISTORY_LENGTH:]

    @callback
    def async_get_history(self) -> list[AutoUpdateHistoryEntry]:
        """Return the recent automatic updates, oldest first."""
        return list(self._history)

    @property
    def settings(self) -> AutoUpdateSettings:
        """Return the current settings."""
        return AutoUpdateSettings.from_options(self._entry.options)

    @property
    def unavailable_reason(self) -> AutoUpdateUnavailableReason | None:
        """Return why automatic updates are unavailable, or None if available."""
        data = self._coordinator.data
        if data.os is None:
            return AutoUpdateUnavailableReason.NOT_HOME_ASSISTANT_OS
        if data.supervisor.channel != UpdateChannel.STABLE:
            return AutoUpdateUnavailableReason.NOT_STABLE_CHANNEL
        return None

    @callback
    def async_get_first_seen(self, version: str) -> datetime | None:
        """Return when Supervisor first offered a version."""
        return self._first_seen.get(version)

    @callback
    def async_is_skipped(self, version: str) -> bool:
        """Return if a version must not be installed automatically."""
        return version in self._skipped

    @callback
    def async_skip_version(self, version: str) -> None:
        """Never install a version automatically.

        The update entity forgets a skipped version once a newer one is
        offered. Automatic updates may still pick that older patch, so they
        keep their own list.
        """
        if version in self._skipped:
            return
        self._skipped.add(version)
        self._async_save()

    @callback
    def async_unskip_version(self, version: str) -> None:
        """Allow a skipped version to be installed automatically again."""
        if version not in self._skipped:
            return
        self._skipped.discard(version)
        self._async_save()

    @callback
    def async_get_install_candidate(self, now: datetime) -> str | None:
        """Return the patch release to install automatically, if any.

        That is the newest patch of the running major that is not skipped,
        once it waited long enough since it was first seen. An older patch
        is never installed while a newer one waits; the newer one may fix a
        regression in it. Never newer than what Supervisor offers now, so
        rolling back the version file stops a pulled release.
        """
        core = self._coordinator.data.core
        if core.version is None or core.version_latest is None:
            return None

        running = AwesomeVersion(core.version)
        offered = AwesomeVersion(core.version_latest)
        patches = [
            AwesomeVersion(version)
            for version in self._first_seen
            if _major(version) == _major(core.version)
            and version not in self._skipped
            and running < AwesomeVersion(version) <= offered
        ]
        if not patches:
            return None

        newest = str(max(patches))
        if self._first_seen[newest] + self.settings.delay > now:
            return None
        return newest

    @callback
    def _async_install_time(self, now: datetime) -> datetime | None:
        """Return from when this installation may update in the current window.

        Each installation updates from its own fixed point in the window, so
        not every installation asks for the new version at the same moment.
        The point stays one check before the end, so a check still sees it.
        """
        settings = self.settings
        if (start := _window_start(settings, now)) is None:
            return None
        length = _window_length(settings.window_start, settings.window_end)
        spread = max(length - CHECK_INTERVAL, timedelta(0))
        return start + spread * self._window_offset

    @callback
    def _async_is_unsafe(self) -> bool:
        """Return if the data is stale or another Core update is running."""
        jobs_coordinator = self._hass.data[JOBS_COORDINATOR]
        if (
            not self._coordinator.last_update_success
            or not jobs_coordinator.last_update_success
        ):
            return True

        return any(
            job.done is False and job.name == _BUSY_JOB_NAME
            for job in jobs_coordinator.current_jobs
        )

    @callback
    def _async_is_backing_up(self) -> bool:
        """Return if a backup is running."""
        # Imported here like update_helper does, to keep backup out of startup
        from homeassistant.components.backup import (  # noqa: PLC0415
            DATA_MANAGER,
            IdleEvent,
        )

        # Supervisor's backup job ends before Core uploads to the backup agents
        if (backup_manager := self._hass.data.get(DATA_MANAGER)) is not None and (
            not isinstance(backup_manager.last_event, IdleEvent)
        ):
            return True

        return any(
            job.done is False
            and job.name is not None
            and job.name.startswith(_BUSY_JOB_PREFIX)
            for job in self._hass.data[JOBS_COORDINATOR].current_jobs
        )

    @callback
    def _async_eligible_version(self, now: datetime) -> str | None:
        """Return the version to install, if automatic updates may run."""
        if (
            self.settings.enabled is not True
            or self.unavailable_reason is not None
            or self._hass.config.safe_mode
        ):
            return None

        return self.async_get_install_candidate(now)

    @callback
    def _async_due_version(self, now: datetime) -> str | None:
        """Return the version to install now, if it is time for one."""
        if (
            install_time := self._async_install_time(now)
        ) is None or now < install_time:
            return None

        return self._async_eligible_version(now)

    async def _async_check(self) -> None:
        """Install an eligible patch release when it is time.

        Only looks at the current state, so it gives the same answer no
        matter what made it run.
        """
        # The last update is not settled yet; nothing new before it is
        if self._restored_pending is not None:
            if not self._async_core_update_running():
                await self._async_settle()
            return

        now = dt_util.now()
        if (window := _window_start(self.settings, now)) is None:
            return

        # One attempt per window; a failure must not retry every few minutes.
        # Compared in UTC; a local start in the hour the clocks go back would
        # never match the stored one.
        window = dt_util.as_utc(window)
        if window == self._attempted_window or self._pending is not None:
            return

        if (
            (version := self._async_due_version(now)) is None
            or self._async_is_unsafe()
            or self._async_is_backing_up()
        ):
            return

        # Stored before the update starts; Home Assistant restarts during it
        self._attempted_window = window
        await self._store.async_save(self._data_to_save())

        backup = async_get_update_options(self._hass, self._entry)[
            OPTION_CORE_BACKUP_BEFORE_UPDATE
        ]
        try:
            if backup:
                # Imported here like update_helper does, to keep backup out of
                # startup
                from .backup import backup_core_before_update  # noqa: PLC0415

                await backup_core_before_update(self._hass)

            # Stored before asking Supervisor; Home Assistant restarts during
            # the update and finds out afterwards how it went
            self._pending = PendingUpdate(
                from_version=HA_VERSION,
                to_version=version,
                started=dt_util.utcnow().isoformat(),
            )
            await self._store.async_save(self._data_to_save())

            # Checked again, with nothing awaited until the request: the saves
            # and the backup let the version be skipped or pulled, the data go
            # stale or another update start. The window only bounds the start,
            # so a long backup may run past its end. After our own backup the
            # backup check is left out; it may not show as finished yet.
            if (
                self._async_eligible_version(dt_util.now()) != version
                or self._async_is_unsafe()
                or (not backup and self._async_is_backing_up())
            ):
                _LOGGER.info(
                    "Not installing Home Assistant %s automatically, "
                    "it is no longer due or safe to install",
                    version,
                )
                self._pending = None
                self._async_save()
                return

            _LOGGER.info("Installing Home Assistant %s automatically", version)
            await update_core(self._hass, version, False)
        # The backup can raise SupervisorError directly while finding its location
        except (HomeAssistantError, SupervisorError) as err:
            _LOGGER.error(
                "Automatic update to Home Assistant %s failed: %s", version, err
            )
            self._async_update_failed(version)

    @callback
    def _async_update_failed(self, version: str) -> None:
        """Tell the user an automatic update did not happen.

        Unlike a rollback, the version itself may be fine, so it is tried
        again in the next window.
        """
        self._async_add_history(
            self._pending
            or PendingUpdate(
                from_version=HA_VERSION,
                to_version=version,
                started=dt_util.utcnow().isoformat(),
            ),
            AutoUpdateResult.FAILED,
        )
        self._pending = None
        async_create_issue(
            self._hass,
            DOMAIN,
            ISSUE_FAILED,
            is_fixable=False,
            is_persistent=True,
            severity=IssueSeverity.ERROR,
            translation_key=ISSUE_FAILED,
            translation_placeholders={"version": version},
        )
        self._async_save()

    @callback
    def _async_record_offered_version(self) -> None:
        """Record when a version is first offered, and forget old majors.

        The version file has no release dates, so the wait after a release
        counts from the moment this installation first saw it. That moment
        must never move, or the wait would start over.
        """
        if self.unavailable_reason is not None:
            return

        core = self._coordinator.data.core
        if core.version is None or core.version_latest is None:
            return

        changed = False
        if core.version_latest not in self._first_seen:
            self._first_seen[core.version_latest] = dt_util.utcnow()
            changed = True

        running_major = _major(core.version)
        for version in list(self._first_seen):
            if _major(version) < running_major:
                del self._first_seen[version]
                changed = True
        for version in list(self._skipped):
            if _major(version) < running_major:
                self._skipped.discard(version)
                changed = True

        if changed:
            self._async_save()

    @callback
    def _async_save(self) -> None:
        """Save the data.

        Saved right away as an entry task; unload waits for it, so a reload
        cannot read the store before the change is written.
        """
        self._entry.async_create_task(
            self._hass, self._store.async_save(self._data_to_save())
        )

    @callback
    def _data_to_save(self) -> AutoUpdateStoreData:
        """Return the data to store."""
        return {
            "first_seen": {
                version: first_seen.isoformat()
                for version, first_seen in self._first_seen.items()
            },
            "skipped": sorted(self._skipped),
            "window_offset": self._window_offset,
            "attempted_window": (
                self._attempted_window.isoformat()
                if self._attempted_window is not None
                else None
            ),
            "pending": self._pending,
            "history": self._history,
        }

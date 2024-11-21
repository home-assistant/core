"""Provide persistent configuration for the backup integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Self, TypedDict, Unpack

from cronsim import CronSim

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .manager import BackupManager

# The time of the automatic backup event should be compatible with
# the time of the recorder's nightly job which run at 04:12.
# Run the backup at 04:45.
CRON_PATTERN_DAILY = "45 4 * * *"
CRON_PATTERN_WEEKLY = "45 4 * * {}"
STORE_DELAY_SAVE = 30
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


class StoredBackupConfig(TypedDict):
    """Represent the stored backup config."""

    agent_ids: list[str]
    include_addons: list[str] | None
    include_all_addons: bool
    include_database: bool
    include_folders: list[str] | None
    last_automatic_backup: datetime | None
    max_copies: int | None
    name: str | None
    password: str | None
    schedule: ScheduleState


@dataclass(kw_only=True)
class BackupConfigData:
    """Represent loaded backup config data."""

    agent_ids: list[str] = field(default_factory=list)
    include_addons: list[str] | None = None
    include_all_addons: bool = False
    include_database: bool = True
    include_folders: list[str] | None = None
    last_automatic_backup: datetime | None = None
    max_copies: int | None = None
    name: str | None = None
    password: str | None = None
    schedule: BackupSchedule

    @classmethod
    def from_dict(cls, data: StoredBackupConfig) -> Self:
        """Initialize backup config data from a dict."""
        return cls(
            agent_ids=data["agent_ids"],
            include_addons=data["include_addons"],
            include_all_addons=data["include_all_addons"],
            include_database=data["include_database"],
            include_folders=data["include_folders"],
            last_automatic_backup=data["last_automatic_backup"],
            max_copies=data["max_copies"],
            name=data["name"],
            password=data["password"],
            schedule=BackupSchedule(state=ScheduleState(data["schedule"])),
        )

    def to_dict(self) -> StoredBackupConfig:
        """Convert backup config data to a dict."""
        return StoredBackupConfig(
            agent_ids=self.agent_ids,
            include_addons=self.include_addons,
            include_all_addons=self.include_all_addons,
            include_database=self.include_database,
            include_folders=self.include_folders,
            last_automatic_backup=self.last_automatic_backup,
            max_copies=self.max_copies,
            name=self.name,
            password=self.password,
            schedule=self.schedule.state,
        )


class BackupConfig:
    """Handle backup config."""

    def __init__(self, hass: HomeAssistant, manager: BackupManager) -> None:
        """Initialize backup config."""
        self.data = BackupConfigData(schedule=BackupSchedule())
        self._manager = manager
        self._store: Store[StoredBackupConfig] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )

    async def load(self) -> None:
        """Load config."""
        stored = await self._store.async_load()
        if stored:
            self.data = BackupConfigData.from_dict(stored)

        self.data.schedule.apply(self._manager)

    @callback
    def save(self) -> None:
        """Save config."""
        self._store.async_delay_save(self._data_to_save, STORE_DELAY_SAVE)

    @callback
    def _data_to_save(self) -> StoredBackupConfig:
        """Return data to save."""
        return self.data.to_dict()

    async def update(
        self,
        *,
        max_copies: int | None | UndefinedType = UNDEFINED,
        schedule: ScheduleState | UndefinedType = UNDEFINED,
        **kwargs: Unpack[CreateBackupParametersDict],
    ) -> None:
        """Update config."""
        if max_copies is not UNDEFINED:
            self.data.max_copies = max_copies
        if schedule is not UNDEFINED:
            new_schedule = BackupSchedule(state=schedule)
            if new_schedule != self.data.schedule:
                self.data.schedule = new_schedule
                self.data.schedule.apply(self._manager)

        for param_name, param_value in kwargs.items():
            setattr(self.data, param_name, param_value)

        self.save()


class ScheduleState(StrEnum):
    """Represent the schedule state."""

    NEVER = "never"
    DAILY = "daily"
    MONDAY = "mon"
    TUESDAY = "tue"
    WEDNESDAY = "wed"
    THURSDAY = "thu"
    FRIDAY = "fri"
    SATURDAY = "sat"
    SUNDAY = "sun"


@dataclass(kw_only=True)
class BackupSchedule:
    """Represent the backup schedule."""

    state: ScheduleState = ScheduleState.NEVER

    @callback
    def apply(
        self,
        manager: BackupManager,
    ) -> None:
        """Apply a new schedule.

        There are only three possible state types: never, daily, or weekly.
        """
        if self.state is ScheduleState.NEVER:
            self._unschedule_next(manager)
            return

        if self.state is ScheduleState.DAILY:
            self._schedule_next(CRON_PATTERN_DAILY, manager)
        else:
            self._schedule_next(
                CRON_PATTERN_WEEKLY.format(self.state.value),
                manager,
            )

    @callback
    def _schedule_next(
        self,
        cron_pattern: str,
        manager: BackupManager,
    ) -> None:
        """Schedule the next backup."""
        self._unschedule_next(manager)
        now = dt_util.now()
        seed_time = manager.config.data.last_automatic_backup or now
        cron_event = CronSim(cron_pattern, seed_time)
        next_time = next(cron_event)

        if next_time < now:
            # schedule a backup at next daily time if we missed
            # the last scheduled backup
            cron_event = CronSim(CRON_PATTERN_DAILY, now)
            next_time = next(cron_event)

        async def _create_backup(now: datetime) -> None:
            """Create backup."""
            manager.remove_next_backup_event = None
            config_data = manager.config.data
            config_data.last_automatic_backup = dt_util.now()
            manager.config.save()
            self._schedule_next(cron_pattern, manager)
            await manager.async_create_backup(
                agent_ids=config_data.agent_ids,
                include_addons=config_data.include_addons,
                include_all_addons=config_data.include_all_addons,
                include_database=config_data.include_database,
                include_folders=config_data.include_folders,
                include_homeassistant=True,  # always include HA
                name=config_data.name,
                on_progress=None,
                password=config_data.password,
            )

        manager.remove_next_backup_event = async_track_point_in_time(
            manager.hass, _create_backup, next_time
        )

    @callback
    def _unschedule_next(self, manager: BackupManager) -> None:
        """Unschedule the next backup."""
        if (remove_next_event := manager.remove_next_backup_event) is not None:
            remove_next_event()
            manager.remove_next_backup_event = None


class CreateBackupParametersDict(TypedDict, total=False):
    """Represent the parameters for async_create_backup."""

    agent_ids: list[str]
    include_addons: list[str] | None
    include_all_addons: bool
    include_database: bool
    include_folders: list[str] | None
    name: str | None
    password: str | None

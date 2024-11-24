"""Provide persistent configuration for the backup integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Self, TypedDict

from cronsim import CronSim

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .models import Folder

if TYPE_CHECKING:
    from .manager import Backup, BackupManager

# The time of the automatic backup event should be compatible with
# the time of the recorder's nightly job which runs at 04:12.
# Run the backup at 04:45.
CRON_PATTERN_DAILY = "45 4 * * *"
CRON_PATTERN_WEEKLY = "45 4 * * {}"
STORE_DELAY_SAVE = 30
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


class StoredBackupConfig(TypedDict):
    """Represent the stored backup config."""

    create_backup: StoredCreateBackupConfig
    retention: StoredRetentionConfig
    last_automatic_backup: datetime | None
    schedule: ScheduleState


@dataclass(kw_only=True)
class BackupConfigData:
    """Represent loaded backup config data."""

    create_backup: CreateBackupConfig
    retention_config: RetentionConfig
    last_automatic_backup: datetime | None = None
    schedule: BackupSchedule

    @classmethod
    def from_dict(cls, data: StoredBackupConfig) -> Self:
        """Initialize backup config data from a dict."""
        include_folders_data = data["create_backup"]["include_folders"]
        if include_folders_data:
            include_folders = [Folder(folder) for folder in include_folders_data]
        else:
            include_folders = None
        retention = data["retention"]

        return cls(
            create_backup=CreateBackupConfig(
                agent_ids=data["create_backup"]["agent_ids"],
                include_addons=data["create_backup"]["include_addons"],
                include_all_addons=data["create_backup"]["include_all_addons"],
                include_database=data["create_backup"]["include_database"],
                include_folders=include_folders,
                name=data["create_backup"]["name"],
                password=data["create_backup"]["password"],
            ),
            retention_config=RetentionConfig(
                copies=retention["copies"],
                days=retention["days"],
            ),
            last_automatic_backup=data["last_automatic_backup"],
            schedule=BackupSchedule(state=ScheduleState(data["schedule"])),
        )

    def to_dict(self) -> StoredBackupConfig:
        """Convert backup config data to a dict."""
        return StoredBackupConfig(
            create_backup=self.create_backup.to_dict(),
            retention=self.retention_config.to_dict(),
            last_automatic_backup=self.last_automatic_backup,
            schedule=self.schedule.state,
        )


class BackupConfig:
    """Handle backup config."""

    def __init__(self, hass: HomeAssistant, manager: BackupManager) -> None:
        """Initialize backup config."""
        self.data = BackupConfigData(
            create_backup=CreateBackupConfig(),
            retention_config=RetentionConfig(),
            schedule=BackupSchedule(),
        )
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
        create_backup: CreateBackupParametersDict | UndefinedType = UNDEFINED,
        retention: RetentionParametersDict | UndefinedType = UNDEFINED,
        schedule: ScheduleState | UndefinedType = UNDEFINED,
    ) -> None:
        """Update config."""
        if create_backup is not UNDEFINED:
            self.data.create_backup = replace(self.data.create_backup, **create_backup)
        if retention is not UNDEFINED:
            retention_config = RetentionConfig(**retention)
            if retention_config != self.data.retention_config:
                self.data.retention_config = retention_config
                self.data.retention_config.apply(self._manager)
        if schedule is not UNDEFINED:
            new_schedule = BackupSchedule(state=schedule)
            if new_schedule != self.data.schedule:
                self.data.schedule = new_schedule
                self.data.schedule.apply(self._manager)

        self.save()


@dataclass(kw_only=True)
class RetentionConfig:
    """Represent the backup retention configuration."""

    copies: int | None = None
    days: int | None = None

    def apply(self, manager: BackupManager) -> None:
        """Apply backup retention configuration."""
        if self.days is not None:
            self._schedule_next(manager)
        else:
            self._unschedule_next(manager)

    def to_dict(self) -> StoredRetentionConfig:
        """Convert backup retention configuration to a dict."""
        return StoredRetentionConfig(
            copies=self.copies,
            days=self.days,
        )

    @callback
    def _schedule_next(
        self,
        manager: BackupManager,
    ) -> None:
        """Schedule the next delete after days."""
        self._unschedule_next(manager)

        async def _delete_backups(now: datetime) -> None:
            """Delete backups older than days."""
            self._schedule_next(manager)

            def _backups_filter(backups: dict[str, Backup]) -> dict[str, Backup]:
                """Return backups older than days to delete."""
                # we need to check here since we await before
                # this filter is applied
                if self.days is None:
                    return {}
                now = dt_util.utcnow()
                return {
                    backup_id: backup
                    for backup_id, backup in backups.items()
                    if dt_util.parse_datetime(backup.date, raise_on_error=True)
                    + timedelta(days=self.days)
                    < now
                }

            await _delete_filtered_backups(manager, _backups_filter)

        manager.remove_next_delete_event = async_call_later(
            manager.hass, timedelta(days=1), _delete_backups
        )

    @callback
    def _unschedule_next(self, manager: BackupManager) -> None:
        """Unschedule the next delete after days."""
        if (remove_next_event := manager.remove_next_delete_event) is not None:
            remove_next_event()
            manager.remove_next_delete_event = None


class StoredRetentionConfig(TypedDict):
    """Represent the stored backup retention configuration."""

    copies: int | None
    days: int | None


class RetentionParametersDict(TypedDict, total=False):
    """Represent the parameters for retention."""

    copies: int | None
    days: int | None


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

            # Create the backup
            await manager.async_create_backup(
                agent_ids=config_data.create_backup.agent_ids,
                include_addons=config_data.create_backup.include_addons,
                include_all_addons=config_data.create_backup.include_all_addons,
                include_database=config_data.create_backup.include_database,
                include_folders=config_data.create_backup.include_folders,
                include_homeassistant=True,  # always include HA
                name=config_data.create_backup.name,
                password=config_data.create_backup.password,
            )

            # Delete old backups more numerous than copies

            def _backups_filter(backups: dict[str, Backup]) -> dict[str, Backup]:
                """Return oldest backups more numerous than copies to delete."""
                # we need to check here since we await before
                # this filter is applied
                if config_data.retention_config.copies is None:
                    return {}
                return dict(
                    sorted(
                        backups.items(),
                        key=lambda backup_item: backup_item[1].date,
                    )[: len(backups) - config_data.retention_config.copies]
                )

            await _delete_filtered_backups(manager, _backups_filter)

        manager.remove_next_backup_event = async_track_point_in_time(
            manager.hass, _create_backup, next_time
        )

    @callback
    def _unschedule_next(self, manager: BackupManager) -> None:
        """Unschedule the next backup."""
        if (remove_next_event := manager.remove_next_backup_event) is not None:
            remove_next_event()
            manager.remove_next_backup_event = None


@dataclass(kw_only=True)
class CreateBackupConfig:
    """Represent the config for async_create_backup."""

    agent_ids: list[str] = field(default_factory=list)
    include_addons: list[str] | None = None
    include_all_addons: bool = False
    include_database: bool = True
    include_folders: list[Folder] | None = None
    name: str | None = None
    password: str | None = None

    def to_dict(self) -> StoredCreateBackupConfig:
        """Convert create backup config to a dict."""
        return {
            "agent_ids": self.agent_ids,
            "include_addons": self.include_addons,
            "include_all_addons": self.include_all_addons,
            "include_database": self.include_database,
            "include_folders": self.include_folders,
            "name": self.name,
            "password": self.password,
        }


class StoredCreateBackupConfig(TypedDict):
    """Represent the stored config for async_create_backup."""

    agent_ids: list[str]
    include_addons: list[str] | None
    include_all_addons: bool
    include_database: bool
    include_folders: list[Folder] | None
    name: str | None
    password: str | None


class CreateBackupParametersDict(TypedDict, total=False):
    """Represent the parameters for async_create_backup."""

    agent_ids: list[str]
    include_addons: list[str] | None
    include_all_addons: bool
    include_database: bool
    include_folders: list[Folder] | None
    name: str | None
    password: str | None


async def _delete_filtered_backups(
    manager: BackupManager,
    backup_filter: Callable[[dict[str, Backup]], dict[str, Backup]],
) -> None:
    """Delete backups parsed with a filter.

    :param manager: The backup manager.
    :param backup_filter: A filter that should return the backups to delete.
    """
    backups, get_agent_errors = await manager.async_get_backups()
    if get_agent_errors:
        LOGGER.debug(
            "Error getting backups; continuing anyway: %s",
            get_agent_errors,
        )

    LOGGER.debug("Total backups: %s", backups)

    filtered_backups = backup_filter(backups)

    if not filtered_backups:
        return

    # always delete oldest backup first
    filtered_backups = dict(
        sorted(
            filtered_backups.items(),
            key=lambda backup_item: backup_item[1].date,
        )
    )

    if len(filtered_backups) >= len(backups):
        # Never delete the last backup.
        last_backup = filtered_backups.popitem()
        LOGGER.debug("Keeping the last backup: %s", last_backup)

    LOGGER.debug("Backups to delete: %s", filtered_backups)

    if not filtered_backups:
        return

    backup_ids = list(filtered_backups)
    delete_results = await asyncio.gather(
        *(manager.async_delete_backup(backup_id) for backup_id in filtered_backups)
    )
    agent_errors = {
        backup_id: error
        for backup_id, error in zip(backup_ids, delete_results, strict=True)
        if error
    }
    if agent_errors:
        LOGGER.error(
            "Error deleting old copies: %s",
            agent_errors,
        )

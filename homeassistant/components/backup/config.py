"""Provide persistent configuration for the backup integration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
import datetime as dt
from datetime import datetime, timedelta
from enum import StrEnum
import random
from typing import TYPE_CHECKING, Self, TypedDict

from cronsim import CronSim

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .models import BackupManagerError, Folder

if TYPE_CHECKING:
    from .manager import BackupManager, ManagerBackup

AUTOMATIC_BACKUP_AGENTS_UNAVAILABLE_ISSUE_ID = "automatic_backup_agents_unavailable"

CRON_PATTERN_DAILY = "{m} {h} * * *"
CRON_PATTERN_WEEKLY = "{m} {h} * * {d}"

# The default time for automatic backups to run is at 04:45.
# This time is chosen to be compatible with the time of the recorder's
# nightly job which runs at 04:12.
DEFAULT_BACKUP_TIME = dt.time(4, 45)

# Randomize the start time of the backup by up to 60 minutes to avoid
# all backups running at the same time.
BACKUP_START_TIME_JITTER = 60 * 60


class StoredBackupConfig(TypedDict):
    """Represent the stored backup config."""

    agents: dict[str, StoredAgentConfig]
    automatic_backups_configured: bool
    create_backup: StoredCreateBackupConfig
    last_attempted_automatic_backup: str | None
    last_completed_automatic_backup_id: str | None
    last_completed_automatic_backup: str | None
    retention: StoredRetentionConfig
    schedule: StoredBackupSchedule


@dataclass(kw_only=True)
class BackupConfigData:
    """Represent loaded backup config data."""

    agents: dict[str, AgentConfig]
    automatic_backups_configured: bool  # only used by frontend
    create_backup: CreateBackupConfig
    last_attempted_automatic_backup: datetime | None = None
    last_completed_automatic_backup_id: str | None = None
    last_completed_automatic_backup: datetime | None = None
    retention: RetentionConfig
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

        if last_attempted_str := data["last_attempted_automatic_backup"]:
            last_attempted = dt_util.parse_datetime(last_attempted_str)
        else:
            last_attempted = None

        if last_completed_str := data["last_completed_automatic_backup"]:
            last_completed = dt_util.parse_datetime(last_completed_str)
        else:
            last_completed = None

        if time_str := data["schedule"]["time"]:
            time = dt_util.parse_time(time_str)
        else:
            time = None
        days = [Day(day) for day in data["schedule"]["days"]]
        agents = {}
        for agent_id, agent_data in data["agents"].items():
            protected = agent_data["protected"]
            stored_retention = agent_data["retention"]
            agent_retention: AgentRetentionConfig | None
            if stored_retention:
                agent_retention = AgentRetentionConfig(
                    copies=stored_retention["copies"],
                    days=stored_retention["days"],
                )
            else:
                agent_retention = None
            agent_config = AgentConfig(
                protected=protected,
                retention=agent_retention,
            )
            agents[agent_id] = agent_config

        return cls(
            agents=agents,
            automatic_backups_configured=data["automatic_backups_configured"],
            create_backup=CreateBackupConfig(
                agent_ids=data["create_backup"]["agent_ids"],
                include_addons=data["create_backup"]["include_addons"],
                include_all_addons=data["create_backup"]["include_all_addons"],
                include_database=data["create_backup"]["include_database"],
                include_folders=include_folders,
                name=data["create_backup"]["name"],
                password=data["create_backup"]["password"],
            ),
            last_attempted_automatic_backup=last_attempted,
            last_completed_automatic_backup_id=data[
                "last_completed_automatic_backup_id"
            ],
            last_completed_automatic_backup=last_completed,
            retention=RetentionConfig(
                copies=retention["copies"],
                days=retention["days"],
            ),
            schedule=BackupSchedule(
                days=days,
                recurrence=ScheduleRecurrence(data["schedule"]["recurrence"]),
                state=ScheduleState(data["schedule"].get("state", ScheduleState.NEVER)),
                time=time,
            ),
        )

    def to_dict(self) -> StoredBackupConfig:
        """Convert backup config data to a dict."""
        if self.last_attempted_automatic_backup:
            last_attempted = self.last_attempted_automatic_backup.isoformat()
        else:
            last_attempted = None

        if self.last_completed_automatic_backup:
            last_completed = self.last_completed_automatic_backup.isoformat()
        else:
            last_completed = None

        return StoredBackupConfig(
            agents={
                agent_id: agent.to_dict() for agent_id, agent in self.agents.items()
            },
            automatic_backups_configured=self.automatic_backups_configured,
            create_backup=self.create_backup.to_dict(),
            last_attempted_automatic_backup=last_attempted,
            last_completed_automatic_backup_id=self.last_completed_automatic_backup_id,
            last_completed_automatic_backup=last_completed,
            retention=self.retention.to_dict(),
            schedule=self.schedule.to_dict(),
        )


class BackupConfig:
    """Handle backup config."""

    def __init__(self, hass: HomeAssistant, manager: BackupManager) -> None:
        """Initialize backup config."""
        self.data = BackupConfigData(
            agents={},
            automatic_backups_configured=False,
            create_backup=CreateBackupConfig(),
            retention=RetentionConfig(),
            schedule=BackupSchedule(),
        )
        self._hass = hass
        self._manager = manager

    def load(self, stored_config: StoredBackupConfig) -> None:
        """Load config."""
        self.data = BackupConfigData.from_dict(stored_config)
        self.data.retention.apply(self._manager)
        self.data.schedule.apply(self._manager)

    @callback
    def update(
        self,
        *,
        agents: dict[str, AgentParametersDict] | UndefinedType = UNDEFINED,
        automatic_backups_configured: bool | UndefinedType = UNDEFINED,
        create_backup: CreateBackupParametersDict | UndefinedType = UNDEFINED,
        retention: RetentionParametersDict | UndefinedType = UNDEFINED,
        schedule: ScheduleParametersDict | UndefinedType = UNDEFINED,
    ) -> None:
        """Update config."""
        if agents is not UNDEFINED:
            for agent_id, agent_config in agents.items():
                agent_retention = agent_config.get("retention")
                if agent_retention is None:
                    new_agent_retention = None
                else:
                    new_agent_retention = AgentRetentionConfig(
                        copies=agent_retention.get("copies"),
                        days=agent_retention.get("days"),
                    )
                if agent_id not in self.data.agents:
                    old_agent_retention = None
                    self.data.agents[agent_id] = AgentConfig(
                        protected=agent_config.get("protected", True),
                        retention=new_agent_retention,
                    )
                else:
                    new_agent_config = self.data.agents[agent_id]
                    old_agent_retention = new_agent_config.retention
                    if "protected" in agent_config:
                        new_agent_config = replace(
                            new_agent_config, protected=agent_config["protected"]
                        )
                    if "retention" in agent_config:
                        new_agent_config = replace(
                            new_agent_config, retention=new_agent_retention
                        )
                    self.data.agents[agent_id] = new_agent_config
                if new_agent_retention != old_agent_retention:
                    # There's a single retention application method
                    # for both global and agent retention settings.
                    self.data.retention.apply(self._manager)
        if automatic_backups_configured is not UNDEFINED:
            self.data.automatic_backups_configured = automatic_backups_configured
        if create_backup is not UNDEFINED:
            self.data.create_backup = replace(self.data.create_backup, **create_backup)
            if "agent_ids" in create_backup:
                check_unavailable_agents(self._hass, self._manager)
        if retention is not UNDEFINED:
            new_retention = RetentionConfig(**retention)
            if new_retention != self.data.retention:
                self.data.retention = new_retention
                self.data.retention.apply(self._manager)
        if schedule is not UNDEFINED:
            new_schedule = BackupSchedule(**schedule)
            if new_schedule.to_dict() != self.data.schedule.to_dict():
                self.data.schedule = new_schedule
                self.data.schedule.apply(self._manager)

        self._manager.store.save()


@dataclass(kw_only=True)
class AgentConfig:
    """Represent the config for an agent."""

    protected: bool
    """Agent protected configuration.

    If True, the agent backups are password protected.
    """
    retention: AgentRetentionConfig | None = None
    """Agent retention configuration.

    If None, the global retention configuration is used.
    If not None, the global retention configuration is ignored for this agent.
    If an agent retention configuration is set and both copies and days are None,
    backups will be kept forever for that agent.
    """

    def to_dict(self) -> StoredAgentConfig:
        """Convert agent config to a dict."""
        return {
            "protected": self.protected,
            "retention": self.retention.to_dict() if self.retention else None,
        }


class StoredAgentConfig(TypedDict):
    """Represent the stored config for an agent."""

    protected: bool
    retention: StoredRetentionConfig | None


class AgentParametersDict(TypedDict, total=False):
    """Represent the parameters for an agent."""

    protected: bool
    retention: RetentionParametersDict | None


@dataclass(kw_only=True)
class BaseRetentionConfig:
    """Represent the base backup retention configuration."""

    copies: int | None = None
    days: int | None = None

    def to_dict(self) -> StoredRetentionConfig:
        """Convert backup retention configuration to a dict."""
        return StoredRetentionConfig(
            copies=self.copies,
            days=self.days,
        )


@dataclass(kw_only=True)
class RetentionConfig(BaseRetentionConfig):
    """Represent the backup retention configuration."""

    def apply(self, manager: BackupManager) -> None:
        """Apply backup retention configuration."""
        agents_retention = {
            agent_id: agent_config.retention
            for agent_id, agent_config in manager.config.data.agents.items()
        }

        if self.days is not None or any(
            agent_retention and agent_retention.days is not None
            for agent_retention in agents_retention.values()
        ):
            LOGGER.debug(
                "Scheduling next automatic delete of backups older than %s in 1 day",
                self.days,
            )
            self._schedule_next(manager)
        else:
            LOGGER.debug("Unscheduling next automatic delete")
            self._unschedule_next(manager)

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

            def _delete_filter(
                backups: dict[str, ManagerBackup],
            ) -> dict[str, ManagerBackup]:
                """Return backups older than days to delete."""
                # we need to check here since we await before
                # this filter is applied
                agents_retention = {
                    agent_id: agent_config.retention
                    for agent_id, agent_config in manager.config.data.agents.items()
                }
                has_agents_retention = any(
                    agent_retention for agent_retention in agents_retention.values()
                )
                has_agents_retention_days = any(
                    agent_retention and agent_retention.days is not None
                    for agent_retention in agents_retention.values()
                )
                if (global_days := self.days) is None and not has_agents_retention_days:
                    # No global retention days and no agent retention days
                    return {}

                now = dt_util.utcnow()
                if global_days is not None and not has_agents_retention:
                    # Return early to avoid the longer filtering below.
                    return {
                        backup_id: backup
                        for backup_id, backup in backups.items()
                        if dt_util.parse_datetime(backup.date, raise_on_error=True)
                        + timedelta(days=global_days)
                        < now
                    }

                # If there are any agent retention settings, we need to check
                # the retention settings, for every backup and agent combination.

                backups_to_delete = {}

                for backup_id, backup in backups.items():
                    backup_date = dt_util.parse_datetime(
                        backup.date, raise_on_error=True
                    )
                    delete_from_agents = set(backup.agents)
                    for agent_id in backup.agents:
                        agent_retention = agents_retention.get(agent_id)
                        if agent_retention is None:
                            # This agent does not have a retention setting,
                            # so the global retention setting should be used.
                            if global_days is None:
                                # This agent does not have a retention setting
                                # and the global retention days setting is None,
                                # so this backup should not be deleted.
                                delete_from_agents.discard(agent_id)
                                continue
                            days = global_days
                        elif (agent_days := agent_retention.days) is None:
                            # This agent has a retention setting
                            # where days is set to None,
                            # so the backup should not be deleted.
                            delete_from_agents.discard(agent_id)
                            continue
                        else:
                            # This agent has a retention setting
                            # where days is set to a number,
                            # so that setting should be used.
                            days = agent_days
                        if backup_date + timedelta(days=days) >= now:
                            # This backup is not older than the retention days,
                            # so this agent should not be deleted.
                            delete_from_agents.discard(agent_id)

                    filtered_backup = replace(
                        backup,
                        agents={
                            agent_id: agent_backup_status
                            for agent_id, agent_backup_status in backup.agents.items()
                            if agent_id in delete_from_agents
                        },
                    )
                    backups_to_delete[backup_id] = filtered_backup

                return backups_to_delete

            await manager.async_delete_filtered_backups(
                include_filter=_automatic_backups_filter, delete_filter=_delete_filter
            )

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


class AgentRetentionConfig(BaseRetentionConfig):
    """Represent an agent retention configuration."""


class StoredBackupSchedule(TypedDict):
    """Represent the stored backup schedule configuration."""

    days: list[Day]
    recurrence: ScheduleRecurrence
    state: ScheduleState
    time: str | None


class ScheduleParametersDict(TypedDict, total=False):
    """Represent parameters for backup schedule."""

    days: list[Day]
    recurrence: ScheduleRecurrence
    state: ScheduleState
    time: dt.time | None


class Day(StrEnum):
    """Represent the day(s) in a custom schedule recurrence."""

    MONDAY = "mon"
    TUESDAY = "tue"
    WEDNESDAY = "wed"
    THURSDAY = "thu"
    FRIDAY = "fri"
    SATURDAY = "sat"
    SUNDAY = "sun"


class ScheduleRecurrence(StrEnum):
    """Represent the schedule recurrence."""

    NEVER = "never"
    DAILY = "daily"
    CUSTOM_DAYS = "custom_days"


class ScheduleState(StrEnum):
    """Represent the schedule recurrence.

    This is deprecated and can be remove in HA Core 2025.8.
    """

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

    days: list[Day] = field(default_factory=list)
    recurrence: ScheduleRecurrence = ScheduleRecurrence.NEVER
    # Although no longer used, state is kept for backwards compatibility.
    # It can be removed in HA Core 2025.8.
    state: ScheduleState = ScheduleState.NEVER
    time: dt.time | None = None
    cron_event: CronSim | None = field(init=False, default=None)
    next_automatic_backup: datetime | None = field(init=False, default=None)
    next_automatic_backup_additional = False

    @callback
    def apply(
        self,
        manager: BackupManager,
    ) -> None:
        """Apply a new schedule.

        There are only three possible recurrence types: never, daily, or custom_days
        """
        if self.recurrence is ScheduleRecurrence.NEVER or (
            self.recurrence is ScheduleRecurrence.CUSTOM_DAYS and not self.days
        ):
            self._unschedule_next(manager)
            return

        time = self.time if self.time is not None else DEFAULT_BACKUP_TIME
        if self.recurrence is ScheduleRecurrence.DAILY:
            self._schedule_next(
                CRON_PATTERN_DAILY.format(m=time.minute, h=time.hour),
                manager,
            )
        else:  # ScheduleRecurrence.CUSTOM_DAYS
            self._schedule_next(
                CRON_PATTERN_WEEKLY.format(
                    m=time.minute,
                    h=time.hour,
                    d=",".join(day.value for day in self.days),
                ),
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
        if (cron_event := self.cron_event) is None:
            seed_time = manager.config.data.last_completed_automatic_backup or now
            cron_event = self.cron_event = CronSim(cron_pattern, seed_time)
        next_time = next(cron_event)

        if next_time < now:
            # schedule a backup at next daily time once
            # if we missed the last scheduled backup
            time = self.time if self.time is not None else DEFAULT_BACKUP_TIME
            cron_event = CronSim(
                CRON_PATTERN_DAILY.format(m=time.minute, h=time.hour), now
            )
            next_time = next(cron_event)
            # reseed the cron event attribute
            # add a day to the next time to avoid scheduling at the same time again
            self.cron_event = CronSim(cron_pattern, now + timedelta(days=1))

            # Compare the computed next time with the next time from the cron pattern
            # to determine if an additional backup has been scheduled
            cron_event_configured = CronSim(cron_pattern, now)
            next_configured_time = next(cron_event_configured)
            self.next_automatic_backup_additional = next_time < next_configured_time
        else:
            self.next_automatic_backup_additional = False

        async def _create_backup(now: datetime) -> None:
            """Create backup."""
            manager.remove_next_backup_event = None
            self._schedule_next(cron_pattern, manager)

            # create the backup
            try:
                await manager.async_create_automatic_backup()
            except BackupManagerError as err:
                LOGGER.error("Error creating backup: %s", err)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error creating automatic backup")

        if self.time is None:
            # randomize the start time of the backup by up to 60 minutes if the time is
            # not set to avoid all backups running at the same time
            next_time += timedelta(seconds=random.randint(0, BACKUP_START_TIME_JITTER))
        LOGGER.debug("Scheduling next automatic backup at %s", next_time)
        self.next_automatic_backup = next_time
        manager.remove_next_backup_event = async_track_point_in_time(
            manager.hass, _create_backup, next_time
        )

    def to_dict(self) -> StoredBackupSchedule:
        """Convert backup schedule to a dict."""
        return StoredBackupSchedule(
            days=self.days,
            recurrence=self.recurrence,
            state=self.state,
            time=self.time.isoformat() if self.time else None,
        )

    @callback
    def _unschedule_next(self, manager: BackupManager) -> None:
        """Unschedule the next backup."""
        self.next_automatic_backup = None
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


def _automatic_backups_filter(
    backups: dict[str, ManagerBackup],
) -> dict[str, ManagerBackup]:
    """Return automatic backups."""
    return {
        backup_id: backup
        for backup_id, backup in backups.items()
        if backup.with_automatic_settings
    }


async def delete_backups_exceeding_configured_count(manager: BackupManager) -> None:
    """Delete backups exceeding the configured retention count."""

    def _delete_filter(
        backups: dict[str, ManagerBackup],
    ) -> dict[str, ManagerBackup]:
        """Return oldest backups more numerous than copies to delete."""
        agents_retention = {
            agent_id: agent_config.retention
            for agent_id, agent_config in manager.config.data.agents.items()
        }
        has_agents_retention = any(
            agent_retention for agent_retention in agents_retention.values()
        )
        has_agents_retention_copies = any(
            agent_retention and agent_retention.copies is not None
            for agent_retention in agents_retention.values()
        )
        # we need to check here since we await before
        # this filter is applied
        if (
            global_copies := manager.config.data.retention.copies
        ) is None and not has_agents_retention_copies:
            # No global retention copies and no agent retention copies
            return {}
        if global_copies is not None and not has_agents_retention:
            # Return early to avoid the longer filtering below.
            return dict(
                sorted(
                    backups.items(),
                    key=lambda backup_item: backup_item[1].date,
                )[: max(len(backups) - global_copies, 0)]
            )

        backups_by_agent: dict[str, dict[str, ManagerBackup]] = defaultdict(dict)
        for backup_id, backup in backups.items():
            for agent_id in backup.agents:
                backups_by_agent[agent_id][backup_id] = backup

        backups_to_delete_by_agent: dict[str, dict[str, ManagerBackup]] = defaultdict(
            dict
        )
        for agent_id, agent_backups in backups_by_agent.items():
            agent_retention = agents_retention.get(agent_id)
            if agent_retention is None:
                # This agent does not have a retention setting,
                # so the global retention setting should be used.
                if global_copies is None:
                    # This agent does not have a retention setting
                    # and the global retention copies setting is None,
                    # so backups should not be deleted.
                    continue
                # The global retention setting will be used.
                copies = global_copies
            elif (agent_copies := agent_retention.copies) is None:
                # This agent has a retention setting
                # where copies is set to None,
                # so backups should not be deleted.
                continue
            else:
                # This agent retention setting will be used.
                copies = agent_copies

            backups_to_delete_by_agent[agent_id] = dict(
                sorted(
                    agent_backups.items(),
                    key=lambda backup_item: backup_item[1].date,
                )[: max(len(agent_backups) - copies, 0)]
            )

        backup_ids_to_delete: dict[str, set[str]] = defaultdict(set)
        for agent_id, to_delete in backups_to_delete_by_agent.items():
            for backup_id in to_delete:
                backup_ids_to_delete[backup_id].add(agent_id)
        backups_to_delete: dict[str, ManagerBackup] = {}
        for backup_id, agent_ids in backup_ids_to_delete.items():
            backup = backups[backup_id]
            # filter the backup to only include the agents that should be deleted
            filtered_backup = replace(
                backup,
                agents={
                    agent_id: agent_backup_status
                    for agent_id, agent_backup_status in backup.agents.items()
                    if agent_id in agent_ids
                },
            )
            backups_to_delete[backup_id] = filtered_backup
        return backups_to_delete

    await manager.async_delete_filtered_backups(
        include_filter=_automatic_backups_filter, delete_filter=_delete_filter
    )


@callback
def check_unavailable_agents(hass: HomeAssistant, manager: BackupManager) -> None:
    """Check for unavailable agents."""
    if missing_agent_ids := set(manager.config.data.create_backup.agent_ids) - set(
        manager.backup_agents
    ):
        LOGGER.debug(
            "Agents %s are configured for automatic backup but are unavailable",
            missing_agent_ids,
        )

    # Remove issues for unavailable agents that are not unavailable anymore.
    issue_registry = ir.async_get(hass)
    existing_missing_agent_issue_ids = {
        issue_id
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN
        and issue_id.startswith(AUTOMATIC_BACKUP_AGENTS_UNAVAILABLE_ISSUE_ID)
    }
    current_missing_agent_issue_ids = {
        f"{AUTOMATIC_BACKUP_AGENTS_UNAVAILABLE_ISSUE_ID}_{agent_id}": agent_id
        for agent_id in missing_agent_ids
    }
    for issue_id in existing_missing_agent_issue_ids - set(
        current_missing_agent_issue_ids
    ):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    for issue_id, agent_id in current_missing_agent_issue_ids.items():
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            learn_more_url="homeassistant://config/backup",
            severity=ir.IssueSeverity.WARNING,
            translation_key="automatic_backup_agents_unavailable",
            translation_placeholders={
                "agent_id": agent_id,
                "backup_settings": "/config/backup/settings",
            },
        )

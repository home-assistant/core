"""Support for recording details."""

from __future__ import annotations

import abc
import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
import logging
import threading
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.typing import UndefinedType
from homeassistant.util.event_type import EventType

from . import entity_registry, purge, statistics
from .const import DOMAIN
from .db_schema import Statistics, StatisticsShortTerm
from .models import StatisticData, StatisticMetaData
from .util import periodic_db_cleanups, session_scope

_LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:
    from .core import Recorder


@dataclass(slots=True)
class RecorderTask:
    """ABC for recorder tasks."""

    commit_before = True

    @abc.abstractmethod
    def run(self, instance: Recorder) -> None:
        """Handle the task."""


@dataclass(slots=True)
class ChangeStatisticsUnitTask(RecorderTask):
    """Object to store statistics_id and unit to convert unit of statistics."""

    statistic_id: str
    new_unit_of_measurement: str
    old_unit_of_measurement: str

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        statistics.change_statistics_unit(
            instance,
            self.statistic_id,
            self.new_unit_of_measurement,
            self.old_unit_of_measurement,
        )


@dataclass(slots=True)
class ClearStatisticsTask(RecorderTask):
    """Object to store statistics_ids which for which to remove statistics."""

    statistic_ids: list[str]

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        statistics.clear_statistics(instance, self.statistic_ids)


@dataclass(slots=True)
class UpdateStatisticsMetadataTask(RecorderTask):
    """Object to store statistics_id and unit for update of statistics metadata."""

    statistic_id: str
    new_statistic_id: str | None | UndefinedType
    new_unit_of_measurement: str | None | UndefinedType

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        statistics.update_statistics_metadata(
            instance,
            self.statistic_id,
            self.new_statistic_id,
            self.new_unit_of_measurement,
        )


@dataclass(slots=True)
class UpdateStatesMetadataTask(RecorderTask):
    """Task to update states metadata."""

    entity_id: str
    new_entity_id: str

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        entity_registry.update_states_metadata(
            instance,
            self.entity_id,
            self.new_entity_id,
        )


@dataclass(slots=True)
class PurgeTask(RecorderTask):
    """Object to store information about purge task."""

    purge_before: datetime
    repack: bool
    apply_filter: bool

    def run(self, instance: Recorder) -> None:
        """Purge the database."""
        if purge.purge_old_data(
            instance, self.purge_before, self.repack, self.apply_filter
        ):
            with instance.get_session() as session:
                instance.recorder_runs_manager.load_from_db(session)
            # We always need to do the db cleanups after a purge
            # is finished to ensure the WAL checkpoint and other
            # tasks happen after a vacuum.
            periodic_db_cleanups(instance)
            return
        # Schedule a new purge task if this one didn't finish
        instance.queue_task(
            PurgeTask(self.purge_before, self.repack, self.apply_filter)
        )


@dataclass(slots=True)
class PurgeEntitiesTask(RecorderTask):
    """Object to store entity information about purge task."""

    entity_filter: Callable[[str], bool]
    purge_before: datetime

    def run(self, instance: Recorder) -> None:
        """Purge entities from the database."""
        if purge.purge_entity_data(instance, self.entity_filter, self.purge_before):
            return
        # Schedule a new purge task if this one didn't finish
        instance.queue_task(PurgeEntitiesTask(self.entity_filter, self.purge_before))


@dataclass(slots=True)
class PerodicCleanupTask(RecorderTask):
    """An object to insert into the recorder to trigger cleanup tasks.

    Trigger cleanup tasks when auto purge is disabled.
    """

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        periodic_db_cleanups(instance)


@dataclass(slots=True)
class StatisticsTask(RecorderTask):
    """An object to insert into the recorder queue to run a statistics task."""

    start: datetime
    fire_events: bool

    def run(self, instance: Recorder) -> None:
        """Run statistics task."""
        if statistics.compile_statistics(instance, self.start, self.fire_events):
            return
        # Schedule a new statistics task if this one didn't finish
        instance.queue_task(StatisticsTask(self.start, self.fire_events))


@dataclass(slots=True)
class CompileMissingStatisticsTask(RecorderTask):
    """An object to insert into the recorder queue to run a compile missing statistics."""

    def run(self, instance: Recorder) -> None:
        """Run statistics task to compile missing statistics."""
        if statistics.compile_missing_statistics(instance):
            return
        # Schedule a new statistics task if this one didn't finish
        instance.queue_task(CompileMissingStatisticsTask())


@dataclass(slots=True)
class ImportStatisticsTask(RecorderTask):
    """An object to insert into the recorder queue to run an import statistics task."""

    metadata: StatisticMetaData
    statistics: Iterable[StatisticData]
    table: type[Statistics | StatisticsShortTerm]

    def run(self, instance: Recorder) -> None:
        """Run statistics task."""
        if statistics.import_statistics(
            instance, self.metadata, self.statistics, self.table
        ):
            return
        # Schedule a new statistics task if this one didn't finish
        instance.queue_task(
            ImportStatisticsTask(self.metadata, self.statistics, self.table)
        )


@dataclass(slots=True)
class AdjustStatisticsTask(RecorderTask):
    """An object to insert into the recorder queue to run an adjust statistics task."""

    statistic_id: str
    start_time: datetime
    sum_adjustment: float
    adjustment_unit: str

    def run(self, instance: Recorder) -> None:
        """Run statistics task."""
        if statistics.adjust_statistics(
            instance,
            self.statistic_id,
            self.start_time,
            self.sum_adjustment,
            self.adjustment_unit,
        ):
            return
        # Schedule a new adjust statistics task if this one didn't finish
        instance.queue_task(
            AdjustStatisticsTask(
                self.statistic_id,
                self.start_time,
                self.sum_adjustment,
                self.adjustment_unit,
            )
        )


@dataclass(slots=True)
class WaitTask(RecorderTask):
    """An object to insert into the recorder queue.

    Tell it set the _queue_watch event.
    """

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance._queue_watch.set()  # noqa: SLF001


@dataclass(slots=True)
class DatabaseLockTask(RecorderTask):
    """An object to insert into the recorder queue to prevent writes to the database."""

    database_locked: asyncio.Event
    database_unlock: threading.Event
    queue_overflow: bool

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance._lock_database(self)  # noqa: SLF001


@dataclass(slots=True)
class StopTask(RecorderTask):
    """An object to insert into the recorder queue to stop the event handler."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance.stop_requested = True


@dataclass(slots=True)
class KeepAliveTask(RecorderTask):
    """A keep alive to be sent."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance._send_keep_alive()  # noqa: SLF001


@dataclass(slots=True)
class CommitTask(RecorderTask):
    """Commit the event session."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance._commit_event_session_or_retry()  # noqa: SLF001


@dataclass(slots=True)
class AddRecorderPlatformTask(RecorderTask):
    """Add a recorder platform."""

    domain: str
    platform: Any
    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        hass = instance.hass
        domain = self.domain
        platform = self.platform
        platforms: dict[str, Any] = hass.data[DOMAIN].recorder_platforms
        platforms[domain] = platform


@dataclass(slots=True)
class SynchronizeTask(RecorderTask):
    """Ensure all pending data has been committed."""

    # commit_before is the default
    event: asyncio.Event

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        # Does not use a tracked task to avoid
        # blocking shutdown if the recorder is broken
        instance.hass.loop.call_soon_threadsafe(self.event.set)


@dataclass(slots=True)
class AdjustLRUSizeTask(RecorderTask):
    """An object to insert into the recorder queue to adjust the LRU size."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task to adjust the size."""
        instance._adjust_lru_size()  # noqa: SLF001


@dataclass(slots=True)
class RefreshEventTypesTask(RecorderTask):
    """An object to insert into the recorder queue to refresh event types."""

    event_types: list[EventType[Any] | str]

    def run(self, instance: Recorder) -> None:
        """Refresh event types."""
        with session_scope(session=instance.get_session(), read_only=True) as session:
            instance.event_type_manager.get_many(
                self.event_types, session, from_recorder=True
            )

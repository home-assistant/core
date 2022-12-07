"""Support for recording details."""
from __future__ import annotations

import abc
import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
import threading
from typing import TYPE_CHECKING, Any

from homeassistant.core import Event
from homeassistant.helpers.typing import UndefinedType

from . import purge, statistics
from .const import DOMAIN, EXCLUDE_ATTRIBUTES
from .db_schema import Statistics, StatisticsShortTerm
from .models import StatisticData, StatisticMetaData
from .util import periodic_db_cleanups

if TYPE_CHECKING:
    from .core import Recorder


class RecorderTask(abc.ABC):
    """ABC for recorder tasks."""

    commit_before = True

    @abc.abstractmethod
    def run(self, instance: Recorder) -> None:
        """Handle the task."""


@dataclass
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


@dataclass
class ClearStatisticsTask(RecorderTask):
    """Object to store statistics_ids which for which to remove statistics."""

    statistic_ids: list[str]

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        statistics.clear_statistics(instance, self.statistic_ids)


@dataclass
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


@dataclass
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
                instance.run_history.load_from_db(session)
            # We always need to do the db cleanups after a purge
            # is finished to ensure the WAL checkpoint and other
            # tasks happen after a vacuum.
            periodic_db_cleanups(instance)
            return
        # Schedule a new purge task if this one didn't finish
        instance.queue_task(
            PurgeTask(self.purge_before, self.repack, self.apply_filter)
        )


@dataclass
class PurgeEntitiesTask(RecorderTask):
    """Object to store entity information about purge task."""

    entity_filter: Callable[[str], bool]

    def run(self, instance: Recorder) -> None:
        """Purge entities from the database."""
        if purge.purge_entity_data(instance, self.entity_filter):
            return
        # Schedule a new purge task if this one didn't finish
        instance.queue_task(PurgeEntitiesTask(self.entity_filter))


@dataclass
class PerodicCleanupTask(RecorderTask):
    """An object to insert into the recorder to trigger cleanup tasks when auto purge is disabled."""

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        periodic_db_cleanups(instance)


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
class WaitTask(RecorderTask):
    """An object to insert into the recorder queue to tell it set the _queue_watch event."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance._queue_watch.set()  # pylint: disable=[protected-access]


@dataclass
class DatabaseLockTask(RecorderTask):
    """An object to insert into the recorder queue to prevent writes to the database."""

    database_locked: asyncio.Event
    database_unlock: threading.Event
    queue_overflow: bool

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance._lock_database(self)  # pylint: disable=[protected-access]


@dataclass
class StopTask(RecorderTask):
    """An object to insert into the recorder queue to stop the event handler."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance.stop_requested = True


@dataclass
class EventTask(RecorderTask):
    """An event to be processed."""

    event: Event
    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        # pylint: disable-next=[protected-access]
        instance._process_one_event(self.event)


@dataclass
class KeepAliveTask(RecorderTask):
    """A keep alive to be sent."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        # pylint: disable-next=[protected-access]
        instance._send_keep_alive()


@dataclass
class CommitTask(RecorderTask):
    """Commit the event session."""

    commit_before = False

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        # pylint: disable-next=[protected-access]
        instance._commit_event_session_or_retry()


@dataclass
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
        if hasattr(self.platform, "exclude_attributes"):
            hass.data[EXCLUDE_ATTRIBUTES][domain] = platform.exclude_attributes(hass)


@dataclass
class SynchronizeTask(RecorderTask):
    """Ensure all pending data has been committed."""

    # commit_before is the default
    event: asyncio.Event

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        # Does not use a tracked task to avoid
        # blocking shutdown if the recorder is broken
        instance.hass.loop.call_soon_threadsafe(self.event.set)

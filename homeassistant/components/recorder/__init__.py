"""Support for recording details."""
from __future__ import annotations

import abc
import asyncio
from collections.abc import Callable, Iterable
import concurrent.futures
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import queue
import sqlite3
import threading
import time
from typing import Any, TypeVar

from lru import LRU  # pylint: disable=no-name-in-module
from sqlalchemy import create_engine, event as sqlalchemy_event, exc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.pool import StaticPool
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EXCLUDE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED,
    MATCH_ALL,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    convert_include_exclude_filter,
    generate_filter,
)
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
    async_track_utc_time_change,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util

from . import history, migration, purge, statistics, websocket_api
from .const import (
    CONF_DB_INTEGRITY_CHECK,
    DATA_INSTANCE,
    DB_WORKER_PREFIX,
    DOMAIN,
    MAX_QUEUE_BACKLOG,
    SQLITE_URL_PREFIX,
)
from .executor import DBInterruptibleThreadPoolExecutor
from .models import (
    Base,
    Events,
    RecorderRuns,
    StateAttributes,
    States,
    StatisticsRuns,
    process_timestamp,
)
from .pool import POOL_SIZE, RecorderPool
from .util import (
    dburl_to_path,
    end_incomplete_runs,
    move_away_broken_database,
    perodic_db_cleanups,
    session_scope,
    setup_connection_for_dialect,
    validate_or_move_away_sqlite_database,
    write_lock_db_sqlite,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


SERVICE_PURGE = "purge"
SERVICE_PURGE_ENTITIES = "purge_entities"
SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"

ATTR_KEEP_DAYS = "keep_days"
ATTR_REPACK = "repack"
ATTR_APPLY_FILTER = "apply_filter"

SERVICE_PURGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_KEEP_DAYS): cv.positive_int,
        vol.Optional(ATTR_REPACK, default=False): cv.boolean,
        vol.Optional(ATTR_APPLY_FILTER, default=False): cv.boolean,
    }
)

ATTR_DOMAINS = "domains"
ATTR_ENTITY_GLOBS = "entity_globs"

SERVICE_PURGE_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DOMAINS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
).extend(cv.ENTITY_SERVICE_FIELDS)
SERVICE_ENABLE_SCHEMA = vol.Schema({})
SERVICE_DISABLE_SCHEMA = vol.Schema({})

DEFAULT_URL = "sqlite:///{hass_config_path}"
DEFAULT_DB_FILE = "home-assistant_v2.db"
DEFAULT_DB_INTEGRITY_CHECK = True
DEFAULT_DB_MAX_RETRIES = 10
DEFAULT_DB_RETRY_WAIT = 3
DEFAULT_COMMIT_INTERVAL = 1
KEEPALIVE_TIME = 30

# Controls how often we clean up
# States and Events objects
EXPIRE_AFTER_COMMITS = 120

DB_LOCK_TIMEOUT = 30
DB_LOCK_QUEUE_CHECK_TIMEOUT = 1

CONF_AUTO_PURGE = "auto_purge"
CONF_DB_URL = "db_url"
CONF_DB_MAX_RETRIES = "db_max_retries"
CONF_DB_RETRY_WAIT = "db_retry_wait"
CONF_PURGE_KEEP_DAYS = "purge_keep_days"
CONF_PURGE_INTERVAL = "purge_interval"
CONF_EVENT_TYPES = "event_types"
CONF_COMMIT_INTERVAL = "commit_interval"

INVALIDATED_ERR = "Database connection invalidated"
CONNECTIVITY_ERR = "Error in database connectivity during commit"

EXCLUDE_SCHEMA = INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER.extend(
    {vol.Optional(CONF_EVENT_TYPES): vol.All(cv.ensure_list, [cv.string])}
)

FILTER_SCHEMA = INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
    {vol.Optional(CONF_EXCLUDE, default=EXCLUDE_SCHEMA({})): EXCLUDE_SCHEMA}
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=dict): vol.All(
            cv.deprecated(CONF_PURGE_INTERVAL),
            cv.deprecated(CONF_DB_INTEGRITY_CHECK),
            FILTER_SCHEMA.extend(
                {
                    vol.Optional(CONF_AUTO_PURGE, default=True): cv.boolean,
                    vol.Optional(CONF_PURGE_KEEP_DAYS, default=10): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                    vol.Optional(CONF_PURGE_INTERVAL, default=1): cv.positive_int,
                    vol.Optional(CONF_DB_URL): cv.string,
                    vol.Optional(
                        CONF_COMMIT_INTERVAL, default=DEFAULT_COMMIT_INTERVAL
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_DB_MAX_RETRIES, default=DEFAULT_DB_MAX_RETRIES
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_DB_RETRY_WAIT, default=DEFAULT_DB_RETRY_WAIT
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_DB_INTEGRITY_CHECK, default=DEFAULT_DB_INTEGRITY_CHECK
                    ): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


# Pool size must accommodate Recorder thread + All db executors
MAX_DB_EXECUTOR_WORKERS = POOL_SIZE - 1


def get_instance(hass: HomeAssistant) -> Recorder:
    """Get the recorder instance."""
    return hass.data[DATA_INSTANCE]


@bind_hass
def is_entity_recorded(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if an entity is being recorded.

    Async friendly.
    """
    if DATA_INSTANCE not in hass.data:
        return False
    return hass.data[DATA_INSTANCE].entity_filter(entity_id)


def run_information(hass, point_in_time: datetime | None = None):
    """Return information about current run.

    There is also the run that covers point_in_time.
    """
    run_info = run_information_from_instance(hass, point_in_time)
    if run_info:
        return run_info

    with session_scope(hass=hass) as session:
        return run_information_with_session(session, point_in_time)


def run_information_from_instance(hass, point_in_time: datetime | None = None):
    """Return information about current run from the existing instance.

    Does not query the database for older runs.
    """
    ins = hass.data[DATA_INSTANCE]

    if point_in_time is None or point_in_time > ins.recording_start:
        return ins.run_info


def run_information_with_session(session, point_in_time: datetime | None = None):
    """Return information about current run from the database."""
    recorder_runs = RecorderRuns

    query = session.query(recorder_runs)
    if point_in_time:
        query = query.filter(
            (recorder_runs.start < point_in_time) & (recorder_runs.end > point_in_time)
        )

    res = query.first()
    if res:
        session.expunge(res)
    return res


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the recorder."""
    hass.data[DOMAIN] = {}
    conf = config[DOMAIN]
    entity_filter = convert_include_exclude_filter(conf)
    auto_purge = conf[CONF_AUTO_PURGE]
    keep_days = conf[CONF_PURGE_KEEP_DAYS]
    commit_interval = conf[CONF_COMMIT_INTERVAL]
    db_max_retries = conf[CONF_DB_MAX_RETRIES]
    db_retry_wait = conf[CONF_DB_RETRY_WAIT]
    db_url = conf.get(CONF_DB_URL) or DEFAULT_URL.format(
        hass_config_path=hass.config.path(DEFAULT_DB_FILE)
    )
    exclude = conf[CONF_EXCLUDE]
    exclude_t = exclude.get(CONF_EVENT_TYPES, [])
    if EVENT_STATE_CHANGED in exclude_t:
        _LOGGER.warning(
            "State change events are excluded, recorder will not record state changes."
            "This will become an error in Home Assistant Core 2022.2"
        )
    instance = hass.data[DATA_INSTANCE] = Recorder(
        hass=hass,
        auto_purge=auto_purge,
        keep_days=keep_days,
        commit_interval=commit_interval,
        uri=db_url,
        db_max_retries=db_max_retries,
        db_retry_wait=db_retry_wait,
        entity_filter=entity_filter,
        exclude_t=exclude_t,
    )
    instance.async_initialize()
    instance.start()
    _async_register_services(hass, instance)
    history.async_setup(hass)
    statistics.async_setup(hass)
    websocket_api.async_setup(hass)
    await async_process_integration_platforms(hass, DOMAIN, _process_recorder_platform)

    return await instance.async_db_ready


async def _process_recorder_platform(hass, domain, platform):
    """Process a recorder platform."""
    hass.data[DOMAIN][domain] = platform


@callback
def _async_register_services(hass, instance):
    """Register recorder services."""

    async def async_handle_purge_service(service: ServiceCall) -> None:
        """Handle calls to the purge service."""
        instance.do_adhoc_purge(**service.data)

    hass.services.async_register(
        DOMAIN, SERVICE_PURGE, async_handle_purge_service, schema=SERVICE_PURGE_SCHEMA
    )

    async def async_handle_purge_entities_service(service: ServiceCall) -> None:
        """Handle calls to the purge entities service."""
        entity_ids = await async_extract_entity_ids(hass, service)
        domains = service.data.get(ATTR_DOMAINS, [])
        entity_globs = service.data.get(ATTR_ENTITY_GLOBS, [])

        instance.do_adhoc_purge_entities(entity_ids, domains, entity_globs)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PURGE_ENTITIES,
        async_handle_purge_entities_service,
        schema=SERVICE_PURGE_ENTITIES_SCHEMA,
    )

    async def async_handle_enable_service(service: ServiceCall) -> None:
        instance.set_enable(True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE,
        async_handle_enable_service,
        schema=SERVICE_ENABLE_SCHEMA,
    )

    async def async_handle_disable_service(service: ServiceCall) -> None:
        instance.set_enable(False)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE,
        async_handle_disable_service,
        schema=SERVICE_DISABLE_SCHEMA,
    )


class RecorderTask(abc.ABC):
    """ABC for recorder tasks."""

    @abc.abstractmethod
    def run(self, instance: Recorder) -> None:
        """Handle the task."""


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
    unit_of_measurement: str | None

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        statistics.update_statistics_metadata(
            instance, self.statistic_id, self.unit_of_measurement
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
            # We always need to do the db cleanups after a purge
            # is finished to ensure the WAL checkpoint and other
            # tasks happen after a vacuum.
            perodic_db_cleanups(instance)
            return
        # Schedule a new purge task if this one didn't finish
        instance.queue.put(PurgeTask(self.purge_before, self.repack, self.apply_filter))


@dataclass
class PurgeEntitiesTask(RecorderTask):
    """Object to store entity information about purge task."""

    entity_filter: Callable[[str], bool]

    def run(self, instance: Recorder) -> None:
        """Purge entities from the database."""
        if purge.purge_entity_data(instance, self.entity_filter):
            return
        # Schedule a new purge task if this one didn't finish
        instance.queue.put(PurgeEntitiesTask(self.entity_filter))


@dataclass
class PerodicCleanupTask(RecorderTask):
    """An object to insert into the recorder to trigger cleanup tasks when auto purge is disabled."""

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        perodic_db_cleanups(instance)


@dataclass
class StatisticsTask(RecorderTask):
    """An object to insert into the recorder queue to run a statistics task."""

    start: datetime

    def run(self, instance: Recorder) -> None:
        """Run statistics task."""
        if statistics.compile_statistics(instance, self.start):
            return
        # Schedule a new statistics task if this one didn't finish
        instance.queue.put(StatisticsTask(self.start))


@dataclass
class ExternalStatisticsTask(RecorderTask):
    """An object to insert into the recorder queue to run an external statistics task."""

    metadata: dict
    statistics: Iterable[dict]

    def run(self, instance: Recorder) -> None:
        """Run statistics task."""
        if statistics.add_external_statistics(instance, self.metadata, self.statistics):
            return
        # Schedule a new statistics task if this one didn't finish
        instance.queue.put(ExternalStatisticsTask(self.metadata, self.statistics))


@dataclass
class WaitTask(RecorderTask):
    """An object to insert into the recorder queue to tell it set the _queue_watch event."""

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

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance.stop_requested = True


@dataclass
class EventTask(RecorderTask):
    """An object to insert into the recorder queue to stop the event handler."""

    event: bool

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        # pylint: disable-next=[protected-access]
        instance._process_one_event(self.event)


class Recorder(threading.Thread):
    """A threaded recorder class."""

    stop_requested: bool

    def __init__(
        self,
        hass: HomeAssistant,
        auto_purge: bool,
        keep_days: int,
        commit_interval: int,
        uri: str,
        db_max_retries: int,
        db_retry_wait: int,
        entity_filter: Callable[[str], bool],
        exclude_t: list[str],
    ) -> None:
        """Initialize the recorder."""
        threading.Thread.__init__(self, name="Recorder")

        self.hass = hass
        self.auto_purge = auto_purge
        self.keep_days = keep_days
        self.commit_interval = commit_interval
        self.queue: queue.SimpleQueue[RecorderTask] = queue.SimpleQueue()
        self.recording_start = dt_util.utcnow()
        self.db_url = uri
        self.db_max_retries = db_max_retries
        self.db_retry_wait = db_retry_wait
        self.async_db_ready: asyncio.Future = asyncio.Future()
        self.async_recorder_ready = asyncio.Event()
        self._queue_watch = threading.Event()
        self.engine: Engine | None = None
        self.run_info: Any = None

        self.entity_filter = entity_filter
        self.exclude_t = exclude_t

        self._timechanges_seen = 0
        self._commits_without_expire = 0
        self._keepalive_count = 0
        self._old_states: dict[str, States] = {}
        self._state_attributes_ids: LRU = LRU(2048)
        self._pending_state_attributes: dict[str, StateAttributes] = {}
        self._pending_expunge: list[States] = []
        self.event_session = None
        self.get_session = None
        self._completed_first_database_setup = None
        self._event_listener = None
        self.async_migration_event = asyncio.Event()
        self.migration_in_progress = False
        self._queue_watcher = None
        self._db_supports_row_number = True
        self._database_lock_task: DatabaseLockTask | None = None
        self._db_executor: DBInterruptibleThreadPoolExecutor | None = None

        self.enabled = True

    def set_enable(self, enable):
        """Enable or disable recording events and states."""
        self.enabled = enable

    @callback
    def async_start_executor(self):
        """Start the executor."""
        self._db_executor = DBInterruptibleThreadPoolExecutor(
            thread_name_prefix=DB_WORKER_PREFIX,
            max_workers=MAX_DB_EXECUTOR_WORKERS,
            shutdown_hook=self._shutdown_pool,
        )

    def _shutdown_pool(self):
        """Close the dbpool connections in the current thread."""
        if hasattr(self.engine.pool, "shutdown"):
            self.engine.pool.shutdown()

    @callback
    def async_initialize(self):
        """Initialize the recorder."""
        self._event_listener = self.hass.bus.async_listen(
            MATCH_ALL, self.event_listener, event_filter=self._async_event_filter
        )
        self._queue_watcher = async_track_time_interval(
            self.hass, self._async_check_queue, timedelta(minutes=10)
        )

    @callback
    def async_add_executor_job(
        self, target: Callable[..., T], *args: Any
    ) -> asyncio.Future[T]:
        """Add an executor job from within the event loop."""
        return self.hass.loop.run_in_executor(self._db_executor, target, *args)

    def _stop_executor(self) -> None:
        """Stop the executor."""
        assert self._db_executor is not None
        self._db_executor.shutdown()
        self._db_executor = None

    @callback
    def _async_check_queue(self, *_):
        """Periodic check of the queue size to ensure we do not exaust memory.

        The queue grows during migraton or if something really goes wrong.
        """
        size = self.queue.qsize()
        _LOGGER.debug("Recorder queue size is: %s", size)
        if self.queue.qsize() <= MAX_QUEUE_BACKLOG:
            return
        _LOGGER.error(
            "The recorder queue reached the maximum size of %s; Events are no longer being recorded",
            MAX_QUEUE_BACKLOG,
        )
        self._async_stop_queue_watcher_and_event_listener()

    @callback
    def _async_stop_queue_watcher_and_event_listener(self):
        """Stop watching the queue and listening for events."""
        if self._queue_watcher:
            self._queue_watcher()
            self._queue_watcher = None
        if self._event_listener:
            self._event_listener()
            self._event_listener = None

    @callback
    def _async_event_filter(self, event) -> bool:
        """Filter events."""
        if event.event_type in self.exclude_t:
            return False

        if (entity_id := event.data.get(ATTR_ENTITY_ID)) is None:
            return True

        if isinstance(entity_id, str):
            return self.entity_filter(entity_id)

        if isinstance(entity_id, list):
            for eid in entity_id:
                if self.entity_filter(eid):
                    return True
            return False

        # Unknown what it is.
        return True

    def do_adhoc_purge(self, **kwargs):
        """Trigger an adhoc purge retaining keep_days worth of data."""
        keep_days = kwargs.get(ATTR_KEEP_DAYS, self.keep_days)
        repack = kwargs.get(ATTR_REPACK)
        apply_filter = kwargs.get(ATTR_APPLY_FILTER)

        purge_before = dt_util.utcnow() - timedelta(days=keep_days)
        self.queue.put(PurgeTask(purge_before, repack, apply_filter))

    def do_adhoc_purge_entities(self, entity_ids, domains, entity_globs):
        """Trigger an adhoc purge of requested entities."""
        entity_filter = generate_filter(domains, entity_ids, [], [], entity_globs)
        self.queue.put(PurgeEntitiesTask(entity_filter))

    def do_adhoc_statistics(self, **kwargs):
        """Trigger an adhoc statistics run."""
        if not (start := kwargs.get("start")):
            start = statistics.get_start_time()
        self.queue.put(StatisticsTask(start))

    @callback
    def async_register(self, shutdown_task, hass_started):
        """Post connection initialize."""

        def _empty_queue(event):
            """Empty the queue if its still present at final write."""

            # If the queue is full of events to be processed because
            # the database is so broken that every event results in a retry
            # we will never be able to get though the events to shutdown in time.
            #
            # We drain all the events in the queue and then insert
            # an empty one to ensure the next thing the recorder sees
            # is a request to shutdown.
            while True:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
            self.queue.put(StopTask())

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_FINAL_WRITE, _empty_queue)

        def shutdown(event):
            """Shut down the Recorder."""
            if not hass_started.done():
                hass_started.set_result(shutdown_task)
            self.queue.put(StopTask())
            self.hass.add_job(self._async_stop_queue_watcher_and_event_listener)
            self.join()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        if self.hass.state == CoreState.running:
            hass_started.set_result(None)
            return

        @callback
        def async_hass_started(event):
            """Notify that hass has started."""
            hass_started.set_result(None)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, async_hass_started)

    @callback
    def async_connection_failed(self):
        """Connect failed tasks."""
        self.async_db_ready.set_result(False)
        persistent_notification.async_create(
            self.hass,
            "The recorder could not start, check [the logs](/config/logs)",
            "Recorder",
        )
        self._async_stop_queue_watcher_and_event_listener()

    @callback
    def async_connection_success(self):
        """Connect success tasks."""
        self.async_db_ready.set_result(True)
        self.async_start_executor()

    @callback
    def _async_recorder_ready(self):
        """Finish start and mark recorder ready."""
        self._async_setup_periodic_tasks()
        self.async_recorder_ready.set()

    @callback
    def async_nightly_tasks(self, now):
        """Trigger the purge."""
        if self.auto_purge:
            # Purge will schedule the perodic cleanups
            # after it completes to ensure it does not happen
            # until after the database is vacuumed
            purge_before = dt_util.utcnow() - timedelta(days=self.keep_days)
            self.queue.put(PurgeTask(purge_before, repack=False, apply_filter=False))
        else:
            self.queue.put(PerodicCleanupTask())

    @callback
    def async_periodic_statistics(self, now):
        """Trigger the hourly statistics run."""
        start = statistics.get_start_time()
        self.queue.put(StatisticsTask(start))

    @callback
    def async_clear_statistics(self, statistic_ids):
        """Clear statistics for a list of statistic_ids."""
        self.queue.put(ClearStatisticsTask(statistic_ids))

    @callback
    def async_update_statistics_metadata(self, statistic_id, unit_of_measurement):
        """Update statistics metadata for a statistic_id."""
        self.queue.put(UpdateStatisticsMetadataTask(statistic_id, unit_of_measurement))

    @callback
    def async_external_statistics(self, metadata, stats):
        """Schedule external statistics."""
        self.queue.put(ExternalStatisticsTask(metadata, stats))

    @callback
    def _async_setup_periodic_tasks(self):
        """Prepare periodic tasks."""
        if self.hass.is_stopping or not self.get_session:
            # Home Assistant is shutting down
            return

        # Run nightly tasks at 4:12am
        async_track_time_change(
            self.hass, self.async_nightly_tasks, hour=4, minute=12, second=0
        )

        # Compile short term statistics every 5 minutes
        async_track_utc_time_change(
            self.hass, self.async_periodic_statistics, minute=range(0, 60, 5), second=10
        )

    def run(self):
        """Start processing events to save."""
        shutdown_task = object()
        hass_started = concurrent.futures.Future()

        self.hass.add_job(self.async_register, shutdown_task, hass_started)

        current_version = self._setup_recorder()

        if current_version is None:
            self.hass.add_job(self.async_connection_failed)
            return

        schema_is_current = migration.schema_is_current(current_version)
        if schema_is_current:
            self._setup_run()
        else:
            self.migration_in_progress = True

        self.hass.add_job(self.async_connection_success)
        # If shutdown happened before Home Assistant finished starting
        if hass_started.result() is shutdown_task:
            self.migration_in_progress = False
            # Make sure we cleanly close the run if
            # we restart before startup finishes
            self._shutdown()
            return

        # We wait to start the migration until startup has finished
        # since it can be cpu intensive and we do not want it to compete
        # with startup which is also cpu intensive
        if not schema_is_current:
            if self._migrate_schema_and_setup_run(current_version):
                if not self._event_listener:
                    # If the schema migration takes so long that the end
                    # queue watcher safety kicks in because MAX_QUEUE_BACKLOG
                    # is reached, we need to reinitialize the listener.
                    self.hass.add_job(self.async_initialize)
            else:
                persistent_notification.create(
                    self.hass,
                    "The database migration failed, check [the logs](/config/logs)."
                    "Database Migration Failed",
                    "recorder_database_migration",
                )
                self._shutdown()
                return

        _LOGGER.debug("Recorder processing the queue")
        self.hass.add_job(self._async_recorder_ready)
        self._run_event_loop()

    def _run_event_loop(self):
        """Run the event loop for the recorder."""
        # Use a session for the event read loop
        # with a commit every time the event time
        # has changed. This reduces the disk io.
        self.stop_requested = False
        while not self.stop_requested:
            task = self.queue.get()
            try:
                self._process_one_task_or_recover(task)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Error while processing event %s: %s", task, err)

        self._shutdown()

    def _process_one_task_or_recover(self, task: RecorderTask):
        """Process an event, reconnect, or recover a malformed database."""
        try:
            return task.run(self)
        except exc.DatabaseError as err:
            if self._handle_database_error(err):
                return
            _LOGGER.exception(
                "Unhandled database error while processing task %s: %s", task, err
            )
        except SQLAlchemyError as err:
            _LOGGER.exception("SQLAlchemyError error processing task %s: %s", task, err)

        # Reset the session if an SQLAlchemyError (including DatabaseError)
        # happens to rollback and recover
        self._reopen_event_session()

    def _setup_recorder(self) -> None | int:
        """Create connect to the database and get the schema version."""
        tries = 1

        while tries <= self.db_max_retries:
            try:
                self._setup_connection()
                return migration.get_schema_version(self)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Error during connection setup: %s (retrying in %s seconds)",
                    err,
                    self.db_retry_wait,
                )
            tries += 1
            time.sleep(self.db_retry_wait)

        return None

    @callback
    def _async_migration_started(self):
        """Set the migration started event."""
        self.async_migration_event.set()

    def _migrate_schema_and_setup_run(self, current_version) -> bool:
        """Migrate schema to the latest version."""
        persistent_notification.create(
            self.hass,
            "System performance will temporarily degrade during the database upgrade. Do not power down or restart the system until the upgrade completes. Integrations that read the database, such as logbook and history, may return inconsistent results until the upgrade completes.",
            "Database upgrade in progress",
            "recorder_database_migration",
        )
        self.hass.add_job(self._async_migration_started)

        try:
            migration.migrate_schema(self, current_version)
        except exc.DatabaseError as err:
            if self._handle_database_error(err):
                return True
            _LOGGER.exception("Database error during schema migration")
            return False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error during schema migration")
            return False
        else:
            self._setup_run()
            return True
        finally:
            self.migration_in_progress = False
            persistent_notification.dismiss(self.hass, "recorder_database_migration")

    def _lock_database(self, task: DatabaseLockTask):
        @callback
        def _async_set_database_locked(task: DatabaseLockTask):
            task.database_locked.set()

        with write_lock_db_sqlite(self):
            # Notify that lock is being held, wait until database can be used again.
            self.hass.add_job(_async_set_database_locked, task)
            while not task.database_unlock.wait(timeout=DB_LOCK_QUEUE_CHECK_TIMEOUT):
                if self.queue.qsize() > MAX_QUEUE_BACKLOG * 0.9:
                    _LOGGER.warning(
                        "Database queue backlog reached more than 90% of maximum queue "
                        "length while waiting for backup to finish; recorder will now "
                        "resume writing to database. The backup can not be trusted and "
                        "must be restarted"
                    )
                    task.queue_overflow = True
                    break
        _LOGGER.info(
            "Database queue backlog reached %d entries during backup",
            self.queue.qsize(),
        )

    def _process_one_event(self, event):
        if event.event_type == EVENT_TIME_CHANGED:
            self._keepalive_count += 1
            if self._keepalive_count >= KEEPALIVE_TIME:
                self._keepalive_count = 0
                self._send_keep_alive()
            if self.commit_interval:
                self._timechanges_seen += 1
                if self._timechanges_seen >= self.commit_interval:
                    self._timechanges_seen = 0
                    self._commit_event_session_or_retry()
            return

        if not self.enabled:
            return

        try:
            if event.event_type == EVENT_STATE_CHANGED:
                dbevent = Events.from_event(event, event_data="{}")
                dbevent.event_data = None
            else:
                dbevent = Events.from_event(event)
        except (TypeError, ValueError):
            _LOGGER.warning("Event is not JSON serializable: %s", event)
            return

        self.event_session.add(dbevent)
        if event.event_type == EVENT_STATE_CHANGED:
            try:
                dbstate = States.from_event(event)
                dbstate_attributes = StateAttributes.from_event(event)
            except (TypeError, ValueError) as ex:
                _LOGGER.warning(
                    "State is not JSON serializable: %s: %s",
                    event.data.get("new_state"),
                    ex,
                )
                return

            dbstate.attributes = None
            shared_attrs = dbstate_attributes.shared_attrs
            # Matching attributes found in the pending commit
            if pending_attributes := self._pending_state_attributes.get(shared_attrs):
                dbstate.state_attributes = pending_attributes
            # Matching attributes id found in the cache
            elif attributes_id := self._state_attributes_ids.get(shared_attrs):
                dbstate.attributes_id = attributes_id
            # Matching attributes found in the database
            elif (
                attributes := self.event_session.query(StateAttributes.attributes_id)
                .filter(StateAttributes.hash == dbstate_attributes.hash)
                .filter(StateAttributes.shared_attrs == shared_attrs)
                .first()
            ):
                dbstate.attributes_id = attributes[0]
                self._state_attributes_ids[shared_attrs] = attributes[0]
            # No matching attributes found, save them in the DB
            else:
                dbstate.state_attributes = dbstate_attributes
                self._pending_state_attributes[shared_attrs] = dbstate_attributes
                self.event_session.add(dbstate_attributes)

            if old_state := self._old_states.pop(dbstate.entity_id, None):
                if old_state.state_id:
                    dbstate.old_state_id = old_state.state_id
                else:
                    dbstate.old_state = old_state
            if event.data.get("new_state"):
                self._old_states[dbstate.entity_id] = dbstate
                self._pending_expunge.append(dbstate)
            else:
                dbstate.state = None
            self.event_session.add(dbstate)
            dbstate.event = dbevent

        # If they do not have a commit interval
        # than we commit right away
        if not self.commit_interval:
            self._commit_event_session_or_retry()

    def _handle_database_error(self, err):
        """Handle a database error that may result in moving away the corrupt db."""
        if isinstance(err.__cause__, sqlite3.DatabaseError):
            _LOGGER.exception(
                "Unrecoverable sqlite3 database corruption detected: %s", err
            )
            self._handle_sqlite_corruption()
            return True
        return False

    def _commit_event_session_or_retry(self):
        """Commit the event session if there is work to do."""
        if not self.event_session.new and not self.event_session.dirty:
            return
        tries = 1
        while tries <= self.db_max_retries:
            try:
                self._commit_event_session()
                return
            except (exc.InternalError, exc.OperationalError) as err:
                _LOGGER.error(
                    "%s: Error executing query: %s. (retrying in %s seconds)",
                    INVALIDATED_ERR if err.connection_invalidated else CONNECTIVITY_ERR,
                    err,
                    self.db_retry_wait,
                )
                if tries == self.db_max_retries:
                    raise

                tries += 1
                time.sleep(self.db_retry_wait)

    def _commit_event_session(self):
        self._commits_without_expire += 1

        if self._pending_expunge:
            self.event_session.flush()
            for dbstate in self._pending_expunge:
                # Expunge the state so its not expired
                # until we use it later for dbstate.old_state
                if dbstate in self.event_session:
                    self.event_session.expunge(dbstate)
            self._pending_expunge = []
        self._pending_state_attributes = {}
        self.event_session.commit()

        # Expire is an expensive operation (frequently more expensive
        # than the flush and commit itself) so we only
        # do it after EXPIRE_AFTER_COMMITS commits
        if self._commits_without_expire == EXPIRE_AFTER_COMMITS:
            self._commits_without_expire = 0
            self.event_session.expire_all()

    def _handle_sqlite_corruption(self):
        """Handle the sqlite3 database being corrupt."""
        self._close_event_session()
        self._close_connection()
        move_away_broken_database(dburl_to_path(self.db_url))
        self._setup_recorder()
        self._setup_run()

    def _close_event_session(self):
        """Close the event session."""
        self._old_states = {}
        self._state_attributes_ids = {}
        self._pending_state_attributes = {}

        if not self.event_session:
            return

        try:
            self.event_session.rollback()
            self.event_session.close()
        except SQLAlchemyError as err:
            _LOGGER.exception(
                "Error while rolling back and closing the event session: %s", err
            )

    def _reopen_event_session(self):
        """Rollback the event session and reopen it after a failure."""
        self._close_event_session()
        self._open_event_session()

    def _open_event_session(self):
        """Open the event session."""
        self.event_session = self.get_session()
        self.event_session.expire_on_commit = False

    def _send_keep_alive(self):
        """Send a keep alive to keep the db connection open."""
        _LOGGER.debug("Sending keepalive")
        self.event_session.connection().scalar(select([1]))

    @callback
    def event_listener(self, event):
        """Listen for new events and put them in the process queue."""
        self.queue.put(EventTask(event))

    def block_till_done(self):
        """Block till all events processed.

        This is only called in tests.

        This only blocks until the queue is empty
        which does not mean the recorder is done.

        Call tests.common's wait_recording_done
        after calling this to ensure the data
        is in the database.
        """
        self._queue_watch.clear()
        self.queue.put(WaitTask())
        self._queue_watch.wait()

    async def lock_database(self) -> bool:
        """Lock database so it can be backed up safely."""
        if not self.engine or self.engine.dialect.name != "sqlite":
            _LOGGER.debug(
                "Not a SQLite database or not connected, locking not necessary"
            )
            return True

        if self._database_lock_task:
            _LOGGER.warning("Database already locked")
            return False

        database_locked = asyncio.Event()
        task = DatabaseLockTask(database_locked, threading.Event(), False)
        self.queue.put(task)
        try:
            await asyncio.wait_for(database_locked.wait(), timeout=DB_LOCK_TIMEOUT)
        except asyncio.TimeoutError as err:
            task.database_unlock.set()
            raise TimeoutError(
                f"Could not lock database within {DB_LOCK_TIMEOUT} seconds."
            ) from err
        self._database_lock_task = task
        return True

    @callback
    def unlock_database(self) -> bool:
        """Unlock database.

        Returns true if database lock has been held throughout the process.
        """
        if not self.engine or self.engine.dialect.name != "sqlite":
            _LOGGER.debug(
                "Not a SQLite database or not connected, unlocking not necessary"
            )
            return True

        if not self._database_lock_task:
            _LOGGER.warning("Database currently not locked")
            return False

        self._database_lock_task.database_unlock.set()
        success = not self._database_lock_task.queue_overflow

        self._database_lock_task = None

        return success

    def _setup_connection(self):
        """Ensure database is ready to fly."""
        kwargs = {}
        self._completed_first_database_setup = False

        def setup_recorder_connection(dbapi_connection, connection_record):
            """Dbapi specific connection settings."""
            setup_connection_for_dialect(
                self,
                self.engine.dialect.name,
                dbapi_connection,
                not self._completed_first_database_setup,
            )
            self._completed_first_database_setup = True

        if self.db_url == SQLITE_URL_PREFIX or ":memory:" in self.db_url:
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
            kwargs["pool_reset_on_return"] = None
        elif self.db_url.startswith(SQLITE_URL_PREFIX):
            kwargs["poolclass"] = RecorderPool
        else:
            kwargs["echo"] = False

        if self._using_file_sqlite:
            validate_or_move_away_sqlite_database(self.db_url)

        self.engine = create_engine(self.db_url, **kwargs)

        sqlalchemy_event.listen(self.engine, "connect", setup_recorder_connection)

        Base.metadata.create_all(self.engine)
        self.get_session = scoped_session(sessionmaker(bind=self.engine))
        _LOGGER.debug("Connected to recorder database")

    @property
    def _using_file_sqlite(self):
        """Short version to check if we are using sqlite3 as a file."""
        return self.db_url != SQLITE_URL_PREFIX and self.db_url.startswith(
            SQLITE_URL_PREFIX
        )

    def _close_connection(self):
        """Close the connection."""
        self.engine.dispose()
        self.engine = None
        self.get_session = None

    def _setup_run(self):
        """Log the start of the current run and schedule any needed jobs."""
        with session_scope(session=self.get_session()) as session:
            start = self.recording_start
            end_incomplete_runs(session, start)
            self.run_info = RecorderRuns(start=start, created=dt_util.utcnow())
            session.add(self.run_info)
            session.flush()
            session.expunge(self.run_info)
            self._schedule_compile_missing_statistics(session)

        self._open_event_session()

    def _schedule_compile_missing_statistics(self, session: Session) -> None:
        """Add tasks for missing statistics runs."""
        now = dt_util.utcnow()
        last_period_minutes = now.minute - now.minute % 5
        last_period = now.replace(minute=last_period_minutes, second=0, microsecond=0)
        start = now - timedelta(days=self.keep_days)
        start = start.replace(minute=0, second=0, microsecond=0)

        # Find the newest statistics run, if any
        if last_run := session.query(func.max(StatisticsRuns.start)).scalar():
            start = max(start, process_timestamp(last_run) + timedelta(minutes=5))

        # Add tasks
        while start < last_period:
            end = start + timedelta(minutes=5)
            _LOGGER.debug("Compiling missing statistics for %s-%s", start, end)
            self.queue.put(StatisticsTask(start))
            start = end

    def _end_session(self):
        """End the recorder session."""
        if self.event_session is None:
            return
        try:
            self.run_info.end = dt_util.utcnow()
            self.event_session.add(self.run_info)
            self._commit_event_session_or_retry()
            self.event_session.close()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Error saving the event session during shutdown: %s", err)

        self.run_info = None

    def _shutdown(self):
        """Save end time for current run."""
        self.hass.add_job(self._async_stop_queue_watcher_and_event_listener)
        self._stop_executor()
        self._end_session()
        self._close_connection()

    @property
    def recording(self):
        """Return if the recorder is recording."""
        return self._event_listener is not None

"""Support for recording details."""
from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timedelta
import logging
import queue
import sqlite3
import threading
import time
from typing import Any, Callable, NamedTuple

from sqlalchemy import create_engine, event as sqlalchemy_event, exc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker
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
from homeassistant.core import CoreState, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    convert_include_exclude_filter,
)
from homeassistant.helpers.event import async_track_time_interval, track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util

from . import migration, purge
from .const import CONF_DB_INTEGRITY_CHECK, DATA_INSTANCE, DOMAIN, SQLITE_URL_PREFIX
from .models import Base, Events, RecorderRuns, States
from .pool import RecorderPool
from .util import (
    dburl_to_path,
    end_incomplete_runs,
    move_away_broken_database,
    session_scope,
    setup_connection_for_dialect,
    validate_or_move_away_sqlite_database,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_PURGE = "purge"
SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"

ATTR_KEEP_DAYS = "keep_days"
ATTR_REPACK = "repack"
ATTR_APPLY_FILTER = "apply_filter"

MAX_QUEUE_BACKLOG = 30000

SERVICE_PURGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_KEEP_DAYS): cv.positive_int,
        vol.Optional(ATTR_REPACK, default=False): cv.boolean,
        vol.Optional(ATTR_APPLY_FILTER, default=False): cv.boolean,
    }
)
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


@bind_hass
async def async_migration_in_progress(hass: HomeAssistant) -> bool:
    """Determine is a migration is in progress.

    This is a thin wrapper that allows us to change
    out the implementation later.
    """
    if DATA_INSTANCE not in hass.data:
        return False
    return hass.data[DATA_INSTANCE].migration_in_progress


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

    return await instance.async_db_ready


@callback
def _async_register_services(hass, instance):
    """Register recorder services."""

    async def async_handle_purge_service(service):
        """Handle calls to the purge service."""
        instance.do_adhoc_purge(**service.data)

    hass.services.async_register(
        DOMAIN, SERVICE_PURGE, async_handle_purge_service, schema=SERVICE_PURGE_SCHEMA
    )

    async def async_handle_enable_sevice(service):
        instance.set_enable(True)

    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE, async_handle_enable_sevice, schema=SERVICE_ENABLE_SCHEMA
    )

    async def async_handle_disable_service(service):
        instance.set_enable(False)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE,
        async_handle_disable_service,
        schema=SERVICE_DISABLE_SCHEMA,
    )


class PurgeTask(NamedTuple):
    """Object to store information about purge task."""

    keep_days: int
    repack: bool
    apply_filter: bool


class WaitTask:
    """An object to insert into the recorder queue to tell it set the _queue_watch event."""


class Recorder(threading.Thread):
    """A threaded recorder class."""

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
        self.queue: Any = queue.SimpleQueue()
        self.recording_start = dt_util.utcnow()
        self.db_url = uri
        self.db_max_retries = db_max_retries
        self.db_retry_wait = db_retry_wait
        self.async_db_ready = asyncio.Future()
        self.async_recorder_ready = asyncio.Event()
        self._queue_watch = threading.Event()
        self.engine: Any = None
        self.run_info: Any = None

        self.entity_filter = entity_filter
        self.exclude_t = exclude_t

        self._timechanges_seen = 0
        self._commits_without_expire = 0
        self._keepalive_count = 0
        self._old_states = {}
        self._pending_expunge = []
        self.event_session = None
        self.get_session = None
        self._completed_database_setup = None
        self._event_listener = None
        self.async_migration_event = asyncio.Event()
        self.migration_in_progress = False
        self._queue_watcher = None

        self.enabled = True

    def set_enable(self, enable):
        """Enable or disable recording events and states."""
        self.enabled = enable

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
    def _async_event_filter(self, event):
        """Filter events."""
        if event.event_type in self.exclude_t:
            return False

        entity_id = event.data.get(ATTR_ENTITY_ID)
        return bool(entity_id is None or self.entity_filter(entity_id))

    def do_adhoc_purge(self, **kwargs):
        """Trigger an adhoc purge retaining keep_days worth of data."""
        keep_days = kwargs.get(ATTR_KEEP_DAYS, self.keep_days)
        repack = kwargs.get(ATTR_REPACK)
        apply_filter = kwargs.get(ATTR_APPLY_FILTER)

        self.queue.put(PurgeTask(keep_days, repack, apply_filter))

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
            self.queue.put(None)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_FINAL_WRITE, _empty_queue)

        def shutdown(event):
            """Shut down the Recorder."""
            if not hass_started.done():
                hass_started.set_result(shutdown_task)
            self.queue.put(None)
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

    @callback
    def _async_recorder_ready(self):
        """Mark recorder ready."""
        self.async_recorder_ready.set()

    @callback
    def async_purge(self, now):
        """Trigger the purge."""
        self.queue.put(PurgeTask(self.keep_days, repack=False, apply_filter=False))

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
                    # If the schema migration takes so longer that the end
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

        # Start periodic purge
        if self.auto_purge:
            # Purge every night at 4:12am
            track_time_change(self.hass, self.async_purge, hour=4, minute=12, second=0)

        _LOGGER.debug("Recorder processing the queue")
        self.hass.add_job(self._async_recorder_ready)
        self._run_event_loop()

    def _run_event_loop(self):
        """Run the event loop for the recorder."""
        # Use a session for the event read loop
        # with a commit every time the event time
        # has changed. This reduces the disk io.
        while event := self.queue.get():
            try:
                self._process_one_event_or_recover(event)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Error while processing event %s: %s", event, err)

        self._shutdown()

    def _process_one_event_or_recover(self, event):
        """Process an event, reconnect, or recover a malformed database."""
        try:
            self._process_one_event(event)
            return
        except exc.DatabaseError as err:
            if self._handle_database_error(err):
                return
            _LOGGER.exception(
                "Unhandled database error while processing event %s: %s", event, err
            )
        except SQLAlchemyError as err:
            _LOGGER.exception(
                "SQLAlchemyError error processing event %s: %s", event, err
            )

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
                    "Error during connection setup to %s: %s (retrying in %s seconds)",
                    self.db_url,
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

    def _run_purge(self, keep_days, repack, apply_filter):
        """Purge the database."""
        if purge.purge_old_data(self, keep_days, repack, apply_filter):
            return
        # Schedule a new purge task if this one didn't finish
        self.queue.put(PurgeTask(keep_days, repack, apply_filter))

    def _process_one_event(self, event):
        """Process one event."""
        if isinstance(event, PurgeTask):
            self._run_purge(event.keep_days, event.repack, event.apply_filter)
            return
        if isinstance(event, WaitTask):
            self._queue_watch.set()
            return
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
            else:
                dbevent = Events.from_event(event)
            dbevent.created = event.time_fired
            self.event_session.add(dbevent)
        except (TypeError, ValueError):
            _LOGGER.warning("Event is not JSON serializable: %s", event)
            return

        if event.event_type == EVENT_STATE_CHANGED:
            try:
                dbstate = States.from_event(event)
                has_new_state = event.data.get("new_state")
                if dbstate.entity_id in self._old_states:
                    old_state = self._old_states.pop(dbstate.entity_id)
                    if old_state.state_id:
                        dbstate.old_state_id = old_state.state_id
                    else:
                        dbstate.old_state = old_state
                if not has_new_state:
                    dbstate.state = None
                dbstate.event = dbevent
                dbstate.created = event.time_fired
                self.event_session.add(dbstate)
                if has_new_state:
                    self._old_states[dbstate.entity_id] = dbstate
                    self._pending_expunge.append(dbstate)
            except (TypeError, ValueError):
                _LOGGER.warning(
                    "State is not JSON serializable: %s",
                    event.data.get("new_state"),
                )

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
        self.queue.put(event)

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

    def _setup_connection(self):
        """Ensure database is ready to fly."""
        kwargs = {}
        self._completed_database_setup = False

        def setup_recorder_connection(dbapi_connection, connection_record):
            """Dbapi specific connection settings."""
            if self._completed_database_setup:
                return
            self._completed_database_setup = setup_connection_for_dialect(
                self.engine.dialect.name, dbapi_connection
            )

        if self.db_url == SQLITE_URL_PREFIX or ":memory:" in self.db_url:
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
            kwargs["pool_reset_on_return"] = None
        elif self.db_url.startswith("sqlite:"):
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
        """Log the start of the current run."""
        with session_scope(session=self.get_session()) as session:
            start = self.recording_start
            end_incomplete_runs(session, start)
            self.run_info = RecorderRuns(start=start, created=dt_util.utcnow())
            session.add(self.run_info)
            session.flush()
            session.expunge(self.run_info)

        self._open_event_session()

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
        self._end_session()
        self._close_connection()

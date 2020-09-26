"""Support for recording details."""
import asyncio
from collections import namedtuple
import concurrent.futures
from datetime import datetime
import logging
import queue
import threading
import time
from typing import Any, Callable, List, Optional

from sqlalchemy import create_engine, event as sqlalchemy_event, exc, select
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EXCLUDE,
    EVENT_HOMEASSISTANT_START,
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
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from . import migration, purge
from .const import CONF_DB_INTEGRITY_CHECK, DATA_INSTANCE, DOMAIN, SQLITE_URL_PREFIX
from .models import Base, Events, RecorderRuns, States
from .util import session_scope, validate_or_move_away_sqlite_database

_LOGGER = logging.getLogger(__name__)

SERVICE_PURGE = "purge"

ATTR_KEEP_DAYS = "keep_days"
ATTR_REPACK = "repack"

SERVICE_PURGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_KEEP_DAYS): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_REPACK, default=False): cv.boolean,
    }
)

DEFAULT_URL = "sqlite:///{hass_config_path}"
DEFAULT_DB_FILE = "home-assistant_v2.db"
DEFAULT_DB_INTEGRITY_CHECK = True
DEFAULT_DB_MAX_RETRIES = 10
DEFAULT_DB_RETRY_WAIT = 3
KEEPALIVE_TIME = 30

CONF_AUTO_PURGE = "auto_purge"
CONF_DB_URL = "db_url"
CONF_DB_MAX_RETRIES = "db_max_retries"
CONF_DB_RETRY_WAIT = "db_retry_wait"
CONF_PURGE_KEEP_DAYS = "purge_keep_days"
CONF_PURGE_INTERVAL = "purge_interval"
CONF_EVENT_TYPES = "event_types"
CONF_COMMIT_INTERVAL = "commit_interval"

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
            FILTER_SCHEMA.extend(
                {
                    vol.Optional(CONF_AUTO_PURGE, default=True): cv.boolean,
                    vol.Optional(CONF_PURGE_KEEP_DAYS, default=10): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                    vol.Optional(CONF_PURGE_INTERVAL, default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=0)
                    ),
                    vol.Optional(CONF_DB_URL): cv.string,
                    vol.Optional(CONF_COMMIT_INTERVAL, default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=0)
                    ),
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


def run_information(hass, point_in_time: Optional[datetime] = None):
    """Return information about current run.

    There is also the run that covers point_in_time.
    """
    run_info = run_information_from_instance(hass, point_in_time)
    if run_info:
        return run_info

    with session_scope(hass=hass) as session:
        return run_information_with_session(session, point_in_time)


def run_information_from_instance(hass, point_in_time: Optional[datetime] = None):
    """Return information about current run from the existing instance.

    Does not query the database for older runs.
    """
    ins = hass.data[DATA_INSTANCE]

    if point_in_time is None or point_in_time > ins.recording_start:
        return ins.run_info


def run_information_with_session(session, point_in_time: Optional[datetime] = None):
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
    db_integrity_check = conf[CONF_DB_INTEGRITY_CHECK]

    db_url = conf.get(CONF_DB_URL)
    if not db_url:
        db_url = DEFAULT_URL.format(hass_config_path=hass.config.path(DEFAULT_DB_FILE))
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
        db_integrity_check=db_integrity_check,
    )
    instance.async_initialize()
    instance.start()

    async def async_handle_purge_service(service):
        """Handle calls to the purge service."""
        instance.do_adhoc_purge(**service.data)

    hass.services.async_register(
        DOMAIN, SERVICE_PURGE, async_handle_purge_service, schema=SERVICE_PURGE_SCHEMA
    )

    return await instance.async_db_ready


PurgeTask = namedtuple("PurgeTask", ["keep_days", "repack"])


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
        exclude_t: List[str],
        db_integrity_check: bool,
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
        self.db_integrity_check = db_integrity_check
        self.async_db_ready = asyncio.Future()
        self._queue_watch = threading.Event()
        self.engine: Any = None
        self.run_info: Any = None

        self.entity_filter = entity_filter
        self.exclude_t = exclude_t

        self._timechanges_seen = 0
        self._keepalive_count = 0
        self._old_state_ids = {}
        self.event_session = None
        self.get_session = None
        self._completed_database_setup = False

    @callback
    def async_initialize(self):
        """Initialize the recorder."""
        self.hass.bus.async_listen(MATCH_ALL, self.event_listener)

    def do_adhoc_purge(self, **kwargs):
        """Trigger an adhoc purge retaining keep_days worth of data."""
        keep_days = kwargs.get(ATTR_KEEP_DAYS, self.keep_days)
        repack = kwargs.get(ATTR_REPACK)

        self.queue.put(PurgeTask(keep_days, repack))

    def run(self):
        """Start processing events to save."""
        tries = 1
        connected = False

        while not connected and tries <= self.db_max_retries:
            if tries != 1:
                time.sleep(self.db_retry_wait)
            try:
                self._setup_connection()
                migration.migrate_schema(self)
                self._setup_run()
                connected = True
                _LOGGER.debug("Connected to recorder database")
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Error during connection setup: %s (retrying in %s seconds)",
                    err,
                    self.db_retry_wait,
                )
                tries += 1

        if not connected:

            @callback
            def connection_failed():
                """Connect failed tasks."""
                self.async_db_ready.set_result(False)
                persistent_notification.async_create(
                    self.hass,
                    "The recorder could not start, please check the log",
                    "Recorder",
                )

            self.hass.add_job(connection_failed)
            return

        shutdown_task = object()
        hass_started = concurrent.futures.Future()

        @callback
        def register():
            """Post connection initialize."""
            self.async_db_ready.set_result(True)

            def shutdown(event):
                """Shut down the Recorder."""
                if not hass_started.done():
                    hass_started.set_result(shutdown_task)
                self.queue.put(None)
                self.join()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

            if self.hass.state == CoreState.running:
                hass_started.set_result(None)
            else:

                @callback
                def notify_hass_started(event):
                    """Notify that hass has started."""
                    hass_started.set_result(None)

                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_START, notify_hass_started
                )

        self.hass.add_job(register)
        result = hass_started.result()

        # If shutdown happened before Home Assistant finished starting
        if result is shutdown_task:
            return

        # Start periodic purge
        if self.auto_purge:

            @callback
            def async_purge(now):
                """Trigger the purge."""
                self.queue.put(PurgeTask(self.keep_days, repack=False))

            # Purge every night at 4:12am
            self.hass.helpers.event.track_time_change(
                async_purge, hour=4, minute=12, second=0
            )

        self.event_session = self.get_session()
        # Use a session for the event read loop
        # with a commit every time the event time
        # has changed. This reduces the disk io.
        while True:
            event = self.queue.get()
            if event is None:
                self._close_run()
                self._close_connection()
                return
            if isinstance(event, PurgeTask):
                # Schedule a new purge task if this one didn't finish
                if not purge.purge_old_data(self, event.keep_days, event.repack):
                    self.queue.put(PurgeTask(event.keep_days, event.repack))
                continue
            if isinstance(event, WaitTask):
                self._queue_watch.set()
                continue
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
                continue
            if event.event_type in self.exclude_t:
                continue

            entity_id = event.data.get(ATTR_ENTITY_ID)
            if entity_id is not None:
                if not self.entity_filter(entity_id):
                    continue

            try:
                dbevent = Events.from_event(event)
                if event.event_type == EVENT_STATE_CHANGED:
                    dbevent.event_data = "{}"
                self.event_session.add(dbevent)
                self.event_session.flush()
            except (TypeError, ValueError):
                _LOGGER.warning("Event is not JSON serializable: %s", event)
            except Exception as err:  # pylint: disable=broad-except
                # Must catch the exception to prevent the loop from collapsing
                _LOGGER.exception("Error adding event: %s", err)

            if dbevent and event.event_type == EVENT_STATE_CHANGED:
                try:
                    dbstate = States.from_event(event)
                    has_new_state = event.data.get("new_state")
                    dbstate.old_state_id = self._old_state_ids.get(dbstate.entity_id)
                    if not has_new_state:
                        dbstate.state = None
                    dbstate.event_id = dbevent.event_id
                    self.event_session.add(dbstate)
                    self.event_session.flush()
                    if has_new_state:
                        self._old_state_ids[dbstate.entity_id] = dbstate.state_id
                    elif dbstate.entity_id in self._old_state_ids:
                        del self._old_state_ids[dbstate.entity_id]
                except (TypeError, ValueError):
                    _LOGGER.warning(
                        "State is not JSON serializable: %s",
                        event.data.get("new_state"),
                    )
                except Exception as err:  # pylint: disable=broad-except
                    # Must catch the exception to prevent the loop from collapsing
                    _LOGGER.exception("Error adding state change: %s", err)

            # If they do not have a commit interval
            # than we commit right away
            if not self.commit_interval:
                self._commit_event_session_or_retry()

    def _send_keep_alive(self):
        try:
            _LOGGER.debug("Sending keepalive")
            self.event_session.connection().scalar(select([1]))
            return
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.error(
                "Error in database connectivity during keepalive: %s",
                err,
            )
            self._reopen_event_session()

    def _commit_event_session_or_retry(self):
        tries = 1
        while tries <= self.db_max_retries:
            if tries != 1:
                time.sleep(self.db_retry_wait)

            try:
                self._commit_event_session()
                return
            except (exc.InternalError, exc.OperationalError) as err:
                if err.connection_invalidated:
                    _LOGGER.error(
                        "Database connection invalidated: %s. "
                        "(retrying in %s seconds)",
                        err,
                        self.db_retry_wait,
                    )
                else:
                    _LOGGER.error(
                        "Error in database connectivity during commit: %s. "
                        "(retrying in %s seconds)",
                        err,
                        self.db_retry_wait,
                    )
                tries += 1

            except Exception as err:  # pylint: disable=broad-except
                # Must catch the exception to prevent the loop from collapsing
                _LOGGER.exception("Error saving events: %s", err)
                return

        _LOGGER.error(
            "Error in database update. Could not save " "after %d tries. Giving up",
            tries,
        )
        self._reopen_event_session()

    def _reopen_event_session(self):
        try:
            self.event_session.rollback()
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.exception("Error while rolling back event session: %s", err)

        try:
            self.event_session.close()
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.exception("Error while closing event session: %s", err)

        try:
            self.event_session = self.get_session()
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.exception("Error while creating new event session: %s", err)

    def _commit_event_session(self):
        try:
            self.event_session.commit()
        except Exception as err:
            _LOGGER.error("Error executing query: %s", err)
            self.event_session.rollback()
            raise

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

        def setup_recorder_connection(dbapi_connection, connection_record):
            """Dbapi specific connection settings."""
            if self._completed_database_setup:
                return

            # We do not import sqlite3 here so mysql/other
            # users do not have to pay for it to be loaded in
            # memory
            if self.db_url.startswith(SQLITE_URL_PREFIX):
                old_isolation = dbapi_connection.isolation_level
                dbapi_connection.isolation_level = None
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
                dbapi_connection.isolation_level = old_isolation
                # WAL mode only needs to be setup once
                # instead of every time we open the sqlite connection
                # as its persistent and isn't free to call every time.
                self._completed_database_setup = True
            elif self.db_url.startswith("mysql"):
                cursor = dbapi_connection.cursor()
                cursor.execute("SET session wait_timeout=28800")
                cursor.close()

        if self.db_url == SQLITE_URL_PREFIX or ":memory:" in self.db_url:
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
            kwargs["pool_reset_on_return"] = None
        else:
            kwargs["echo"] = False

        if self.db_url != SQLITE_URL_PREFIX and self.db_url.startswith(
            SQLITE_URL_PREFIX
        ):
            with self.hass.timeout.freeze(DOMAIN):
                #
                # Here we run an sqlite3 quick_check.  In the majority
                # of cases, the quick_check takes under 10 seconds.
                #
                # On systems with very large databases and
                # very slow disk or cpus, this can take a while.
                #
                validate_or_move_away_sqlite_database(
                    self.db_url, self.db_integrity_check
                )

        if self.engine is not None:
            self.engine.dispose()

        self.engine = create_engine(self.db_url, **kwargs)

        sqlalchemy_event.listen(self.engine, "connect", setup_recorder_connection)

        Base.metadata.create_all(self.engine)
        self.get_session = scoped_session(sessionmaker(bind=self.engine))

    def _close_connection(self):
        """Close the connection."""
        self.engine.dispose()
        self.engine = None
        self.get_session = None

    def _setup_run(self):
        """Log the start of the current run."""
        with session_scope(session=self.get_session()) as session:
            for run in session.query(RecorderRuns).filter_by(end=None):
                run.closed_incorrect = True
                run.end = self.recording_start
                _LOGGER.warning(
                    "Ended unfinished session (id=%s from %s)", run.run_id, run.start
                )
                session.add(run)

            self.run_info = RecorderRuns(
                start=self.recording_start, created=dt_util.utcnow()
            )
            session.add(self.run_info)
            session.flush()
            session.expunge(self.run_info)

    def _close_run(self):
        """Save end time for current run."""
        if self.event_session is not None:
            self.run_info.end = dt_util.utcnow()
            self.event_session.add(self.run_info)
            self._commit_event_session_or_retry()
            self.event_session.close()

        self.run_info = None

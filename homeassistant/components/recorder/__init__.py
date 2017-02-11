"""
Support for recording details.

Component that records all events and state changes. Allows other components
to query this database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/recorder/
"""
import logging
import queue
import threading
import time
from datetime import timedelta, datetime
from typing import Any, Union, Optional, List, Dict
from contextlib import contextmanager

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_ENTITIES, CONF_EXCLUDE, CONF_DOMAINS,
    CONF_INCLUDE, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED, EVENT_TIME_CHANGED, MATCH_ALL)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, QueryType
import homeassistant.util.dt as dt_util

DOMAIN = 'recorder'

REQUIREMENTS = ['sqlalchemy==1.1.5']

DEFAULT_URL = 'sqlite:///{hass_config_path}'
DEFAULT_DB_FILE = 'home-assistant_v2.db'

CONF_DB_URL = 'db_url'
CONF_PURGE_DAYS = 'purge_days'

RETRIES = 3
CONNECT_RETRY_WAIT = 10
QUERY_RETRY_WAIT = 0.1
ERROR_QUERY = "Error during query: %s"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_PURGE_DAYS):
            vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(CONF_DB_URL): cv.string,
        vol.Optional(CONF_EXCLUDE, default={}): vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        }),
        vol.Optional(CONF_INCLUDE, default={}): vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        })
    })
}, extra=vol.ALLOW_EXTRA)

_INSTANCE = None  # type: Any
_LOGGER = logging.getLogger(__name__)

# These classes will be populated during setup()
# scoped_session, in the same thread session_scope() stays the same
_SESSION = None


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = _SESSION()
    try:
        yield session
        session.commit()
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error(ERROR_QUERY, err)
        session.rollback()
        raise
    finally:
        session.close()


# pylint: disable=invalid-sequence-index
def execute(qry: QueryType) -> List[Any]:
    """Query the database and convert the objects to HA native form.

    This method also retries a few times in the case of stale connections.
    """
    _verify_instance()

    import sqlalchemy.exc
    with session_scope() as session:
        for _ in range(0, RETRIES):
            try:
                return [
                    row for row in
                    (row.to_native() for row in qry)
                    if row is not None]
            except sqlalchemy.exc.SQLAlchemyError as err:
                _LOGGER.error(ERROR_QUERY, err)
                session.rollback()
                time.sleep(QUERY_RETRY_WAIT)
    return []


def run_information(point_in_time: Optional[datetime]=None):
    """Return information about current run.

    There is also the run that covers point_in_time.
    """
    _verify_instance()

    recorder_runs = get_model('RecorderRuns')
    if point_in_time is None or point_in_time > _INSTANCE.recording_start:
        return recorder_runs(
            end=None,
            start=_INSTANCE.recording_start,
            closed_incorrect=False)

    with session_scope() as session:
        res = query(recorder_runs).filter(
            (recorder_runs.start < point_in_time) &
            (recorder_runs.end > point_in_time)).first()
        if res:
            session.expunge(res)
        return res


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup the recorder."""
    global _INSTANCE  # pylint: disable=global-statement

    if _INSTANCE is not None:
        _LOGGER.error("Only a single instance allowed")
        return False

    purge_days = config.get(DOMAIN, {}).get(CONF_PURGE_DAYS)

    db_url = config.get(DOMAIN, {}).get(CONF_DB_URL, None)
    if not db_url:
        db_url = DEFAULT_URL.format(
            hass_config_path=hass.config.path(DEFAULT_DB_FILE))

    include = config.get(DOMAIN, {}).get(CONF_INCLUDE, {})
    exclude = config.get(DOMAIN, {}).get(CONF_EXCLUDE, {})
    _INSTANCE = Recorder(hass, purge_days=purge_days, uri=db_url,
                         include=include, exclude=exclude)

    return True


def query(model_name: Union[str, Any], *args) -> QueryType:
    """Helper to return a query handle."""
    _verify_instance()

    if isinstance(model_name, str):
        return _SESSION().query(get_model(model_name), *args)
    return _SESSION().query(model_name, *args)


def get_model(model_name: str) -> Any:
    """Get a model class."""
    from homeassistant.components.recorder import models
    try:
        return getattr(models, model_name)
    except AttributeError:
        _LOGGER.error("Invalid model name %s", model_name)
        return None


class Recorder(threading.Thread):
    """A threaded recorder class."""

    def __init__(self, hass: HomeAssistant, purge_days: int, uri: str,
                 include: Dict, exclude: Dict) -> None:
        """Initialize the recorder."""
        threading.Thread.__init__(self)

        self.hass = hass
        self.purge_days = purge_days
        self.queue = queue.Queue()  # type: Any
        self.recording_start = dt_util.utcnow()
        self.db_url = uri
        self.db_ready = threading.Event()
        self.engine = None  # type: Any
        self._run = None  # type: Any

        self.include_e = include.get(CONF_ENTITIES, [])
        self.include_d = include.get(CONF_DOMAINS, [])
        self.exclude = exclude.get(CONF_ENTITIES, []) + \
            exclude.get(CONF_DOMAINS, [])

        def start_recording(event):
            """Start recording."""
            self.start()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_recording)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        hass.bus.listen(MATCH_ALL, self.event_listener)

    def run(self):
        """Start processing events to save."""
        from homeassistant.components.recorder.models import Events, States
        import sqlalchemy.exc

        while True:
            try:
                self._setup_connection()
                self._setup_run()
                break
            except sqlalchemy.exc.SQLAlchemyError as err:
                _LOGGER.error("Error during connection setup: %s (retrying "
                              "in %s seconds)", err, CONNECT_RETRY_WAIT)
                time.sleep(CONNECT_RETRY_WAIT)

        if self.purge_days is not None:
            async_track_time_interval(
                self.hass, self._purge_old_data, timedelta(days=2))

        while True:
            event = self.queue.get()

            if event is None:
                self._close_run()
                self._close_connection()
                self.queue.task_done()
                return

            if event.event_type == EVENT_TIME_CHANGED:
                self.queue.task_done()
                continue

            if ATTR_ENTITY_ID in event.data:
                entity_id = event.data[ATTR_ENTITY_ID]
                domain = split_entity_id(entity_id)[0]

                # Exclude entities OR
                # Exclude domains, but include specific entities
                if (entity_id in self.exclude) or \
                        (domain in self.exclude and
                         entity_id not in self.include_e):
                    self.queue.task_done()
                    continue

                # Included domains only (excluded entities above) OR
                # Include entities only, but only if no excludes
                if (self.include_d and domain not in self.include_d) or \
                        (self.include_e and entity_id not in self.include_e
                         and not self.exclude):
                    self.queue.task_done()
                    continue

            with session_scope() as session:
                dbevent = Events.from_event(event)
                self._commit(session, dbevent)

                if event.event_type != EVENT_STATE_CHANGED:
                    self.queue.task_done()
                    continue

                dbstate = States.from_event(event)
                dbstate.event_id = dbevent.event_id
                self._commit(session, dbstate)

            self.queue.task_done()

    @callback
    def event_listener(self, event):
        """Listen for new events and put them in the process queue."""
        self.queue.put(event)

    def shutdown(self, event):
        """Tell the recorder to shut down."""
        global _INSTANCE  # pylint: disable=global-statement
        _INSTANCE = None

        self.queue.put(None)
        self.join()

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()

    def block_till_db_ready(self):
        """Block until the database session is ready."""
        self.db_ready.wait(10)
        while not self.db_ready.is_set():
            _LOGGER.warning('Database not ready, waiting another 10 seconds.')
            self.db_ready.wait(10)

    def _setup_connection(self):
        """Ensure database is ready to fly."""
        global _SESSION  # pylint: disable=invalid-name,global-statement

        import homeassistant.components.recorder.models as models
        from sqlalchemy import create_engine
        from sqlalchemy.orm import scoped_session
        from sqlalchemy.orm import sessionmaker

        if self.db_url == 'sqlite://' or ':memory:' in self.db_url:
            from sqlalchemy.pool import StaticPool
            self.engine = create_engine(
                'sqlite://',
                connect_args={'check_same_thread': False},
                poolclass=StaticPool,
                pool_reset_on_return=None)
        else:
            self.engine = create_engine(self.db_url, echo=False)

        models.Base.metadata.create_all(self.engine)
        session_factory = sessionmaker(bind=self.engine)
        _SESSION = scoped_session(session_factory)
        self._migrate_schema()
        self.db_ready.set()

    def _migrate_schema(self):
        """Check if the schema needs to be upgraded."""
        from homeassistant.components.recorder.models import SCHEMA_VERSION
        schema_changes = get_model('SchemaChanges')
        with session_scope() as session:
            res = session.query(schema_changes).order_by(
                schema_changes.change_id.desc()).first()
            current_version = getattr(res, 'schema_version', None)

            if current_version == SCHEMA_VERSION:
                return
            _LOGGER.debug("Schema version incorrect: %s", current_version)

            if current_version is None:
                current_version = self._inspect_schema_version()
                _LOGGER.debug("No schema version found. Inspected version: %s",
                              current_version)

            for version in range(current_version, SCHEMA_VERSION):
                new_version = version + 1
                _LOGGER.info("Upgrading recorder db schema to version %s",
                             new_version)
                self._apply_update(new_version)
                self._commit(session,
                             schema_changes(schema_version=new_version))
                _LOGGER.info("Upgraded recorder db schema to version %s",
                             new_version)

    def _apply_update(self, new_version):
        """Perform operations to bring schema up to date."""
        from sqlalchemy import Table
        import homeassistant.components.recorder.models as models

        if new_version == 1:
            def create_index(table_name, column_name):
                """Create an index for the specified table and column."""
                table = Table(table_name, models.Base.metadata)
                name = "_".join(("ix", table_name, column_name))
                # Look up the index object that was created from the models
                index = next(idx for idx in table.indexes if idx.name == name)
                _LOGGER.debug("Creating index for table %s column %s",
                              table_name, column_name)
                index.create(self.engine)
                _LOGGER.debug("Index creation done for table %s column %s",
                              table_name, column_name)

            create_index("events", "time_fired")
        else:
            raise ValueError("No schema migration defined for version {}"
                             .format(new_version))

    def _inspect_schema_version(self):
        """Determine the schema version by inspecting the db structure.

        When the schema verison is not present in the db, either db was just
        created with the correct schema, or this is a db created before schema
        versions were tracked. For now, we'll test if the changes for schema
        version 1 are present to make the determination. Eventually this logic
        can be removed and we can assume a new db is being created.
        """
        from sqlalchemy.engine import reflection
        import homeassistant.components.recorder.models as models
        inspector = reflection.Inspector.from_engine(self.engine)
        indexes = inspector.get_indexes("events")
        with session_scope() as session:
            for index in indexes:
                if index['column_names'] == ["time_fired"]:
                    # Schema addition from version 1 detected. New DB.
                    current_version = models.SchemaChanges(
                        schema_version=models.SCHEMA_VERSION)
                    self._commit(session, current_version)
                    return models.SCHEMA_VERSION

            # Version 1 schema changes not found, this db needs to be migrated.
            current_version = models.SchemaChanges(schema_version=0)
            self._commit(session, current_version)
            return current_version.schema_version

    def _close_connection(self):
        """Close the connection."""
        global _SESSION  # pylint: disable=invalid-name,global-statement
        self.engine.dispose()
        self.engine = None
        _SESSION = None

    def _setup_run(self):
        """Log the start of the current run."""
        recorder_runs = get_model('RecorderRuns')
        with session_scope() as session:
            for run in query('RecorderRuns').filter_by(end=None):
                run.closed_incorrect = True
                run.end = self.recording_start
                _LOGGER.warning("Ended unfinished session (id=%s from %s)",
                                run.run_id, run.start)
                session.add(run)

                _LOGGER.warning("Found unfinished sessions")

            self._run = recorder_runs(
                start=self.recording_start,
                created=dt_util.utcnow()
            )
            self._commit(session, self._run)

    def _close_run(self):
        """Save end time for current run."""
        with session_scope() as session:
            self._run.end = dt_util.utcnow()
            self._commit(session, self._run)
        self._run = None

    def _purge_old_data(self, _=None):
        """Purge events and states older than purge_days ago."""
        from homeassistant.components.recorder.models import Events, States

        if not self.purge_days or self.purge_days < 1:
            _LOGGER.debug("purge_days set to %s, will not purge any old data.",
                          self.purge_days)
            return

        purge_before = dt_util.utcnow() - timedelta(days=self.purge_days)

        def _purge_states(session):
            deleted_rows = session.query(States) \
                                  .filter((States.created < purge_before)) \
                                  .delete(synchronize_session=False)
            _LOGGER.debug("Deleted %s states", deleted_rows)

        with session_scope() as session:
            if self._commit(session, _purge_states):
                _LOGGER.info("Purged states created before %s", purge_before)

        def _purge_events(session):
            deleted_rows = session.query(Events) \
                                  .filter((Events.created < purge_before)) \
                                  .delete(synchronize_session=False)
            _LOGGER.debug("Deleted %s events", deleted_rows)

        with session_scope() as session:
            if self._commit(session, _purge_events):
                _LOGGER.info("Purged events created before %s", purge_before)

        # Execute sqlite vacuum command to free up space on disk
        if self.engine.driver == 'sqlite':
            _LOGGER.info("Vacuuming SQLite to free space")
            self.engine.execute("VACUUM")

    @staticmethod
    def _commit(session, work):
        """Commit & retry work: Either a model or in a function."""
        import sqlalchemy.exc
        for _ in range(0, RETRIES):
            try:
                if callable(work):
                    work(session)
                else:
                    session.add(work)
                session.commit()
                return True
            except sqlalchemy.exc.OperationalError as err:
                _LOGGER.error(ERROR_QUERY, err)
                session.rollback()
                time.sleep(QUERY_RETRY_WAIT)
        return False


def _verify_instance() -> None:
    """Throw error if recorder not initialized."""
    if _INSTANCE is None:
        raise RuntimeError("Recorder not initialized.")

    ident = _INSTANCE.hass.loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError('Cannot be called from within the event loop')

    _INSTANCE.block_till_db_ready()

"""
Support for recording details.

Component that records all events and state changes. Allows other components
to query this database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/recorder/
"""
import asyncio
import logging
import queue
import threading
import time
from datetime import timedelta, datetime
from typing import Any, Union, Optional, List

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import (EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED,
                                 EVENT_TIME_CHANGED, MATCH_ALL)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, QueryType
import homeassistant.util.dt as dt_util

DOMAIN = "recorder"

REQUIREMENTS = ['sqlalchemy==1.0.15']

DEFAULT_URL = "sqlite:///{hass_config_path}"
DEFAULT_DB_FILE = "home-assistant_v2.db"

CONF_DB_URL = "db_url"
CONF_PURGE_DAYS = "purge_days"

RETRIES = 3
CONNECT_RETRY_WAIT = 10
QUERY_RETRY_WAIT = 0.1

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_PURGE_DAYS):
            vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(CONF_DB_URL): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

_INSTANCE = None  # type: Any
_LOGGER = logging.getLogger(__name__)

# These classes will be populated during setup()
# pylint: disable=invalid-name,no-member
Session = None  # pylint: disable=no-member


def execute(q: QueryType) \
        -> List[Any]:  # pylint: disable=invalid-sequence-index
    """Query the database and convert the objects to HA native form.

    This method also retries a few times in the case of stale connections.
    """
    import sqlalchemy.exc
    try:
        for _ in range(0, RETRIES):
            try:
                return [
                    row for row in
                    (row.to_native() for row in q)
                    if row is not None]
            except sqlalchemy.exc.SQLAlchemyError as e:
                log_error(e, retry_wait=QUERY_RETRY_WAIT, rollback=True)
    finally:
        Session.close()
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

    return query('RecorderRuns').filter(
        (recorder_runs.start < point_in_time) &
        (recorder_runs.end > point_in_time)).first()


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup the recorder."""
    global _INSTANCE  # pylint: disable=global-statement

    if _INSTANCE is not None:
        _LOGGER.error('Only a single instance allowed.')
        return False

    purge_days = config.get(DOMAIN, {}).get(CONF_PURGE_DAYS)

    db_url = config.get(DOMAIN, {}).get(CONF_DB_URL, None)
    if not db_url:
        db_url = DEFAULT_URL.format(
            hass_config_path=hass.config.path(DEFAULT_DB_FILE))

    _INSTANCE = Recorder(hass, purge_days=purge_days, uri=db_url)

    return True


def query(model_name: Union[str, Any], *args) -> QueryType:
    """Helper to return a query handle."""
    _verify_instance()

    if isinstance(model_name, str):
        return Session.query(get_model(model_name), *args)
    return Session.query(model_name, *args)


def get_model(model_name: str) -> Any:
    """Get a model class."""
    from homeassistant.components.recorder import models
    try:
        return getattr(models, model_name)
    except AttributeError:
        _LOGGER.error("Invalid model name %s", model_name)
        return None


def log_error(e: Exception, retry_wait: Optional[float]=0,
              rollback: Optional[bool]=True,
              message: Optional[str]="Error during query: %s") -> None:
    """Log about SQLAlchemy errors in a sane manner."""
    import sqlalchemy.exc
    if not isinstance(e, sqlalchemy.exc.OperationalError):
        _LOGGER.exception(str(e))
    else:
        _LOGGER.error(message, str(e))
    if rollback:
        Session.rollback()
    if retry_wait:
        _LOGGER.info("Retrying in %s seconds", retry_wait)
        time.sleep(retry_wait)


class Recorder(threading.Thread):
    """A threaded recorder class."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass: HomeAssistant, purge_days: int, uri: str) \
            -> None:
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
            except sqlalchemy.exc.SQLAlchemyError as e:
                log_error(e, retry_wait=CONNECT_RETRY_WAIT, rollback=False,
                          message="Error during connection setup: %s")

        if self.purge_days is not None:
            def purge_ticker(event):
                """Rerun purge every second day."""
                self._purge_old_data()
                track_point_in_utc_time(self.hass, purge_ticker,
                                        dt_util.utcnow() + timedelta(days=2))
            track_point_in_utc_time(self.hass, purge_ticker,
                                    dt_util.utcnow() + timedelta(minutes=5))

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

            dbevent = Events.from_event(event)
            self._commit(dbevent)

            if event.event_type != EVENT_STATE_CHANGED:
                self.queue.task_done()
                continue

            dbstate = States.from_event(event)
            dbstate.event_id = dbevent.event_id
            self._commit(dbstate)

            self.queue.task_done()

    @asyncio.coroutine
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
        self.db_ready.wait()

    def _setup_connection(self):
        """Ensure database is ready to fly."""
        global Session  # pylint: disable=global-statement

        import homeassistant.components.recorder.models as models
        from sqlalchemy import create_engine
        from sqlalchemy.orm import scoped_session
        from sqlalchemy.orm import sessionmaker

        if self.db_url == 'sqlite://' or ':memory:' in self.db_url:
            from sqlalchemy.pool import StaticPool
            self.engine = create_engine(
                'sqlite://',
                connect_args={'check_same_thread': False},
                poolclass=StaticPool)
        else:
            self.engine = create_engine(self.db_url, echo=False)

        models.Base.metadata.create_all(self.engine)
        session_factory = sessionmaker(bind=self.engine)
        Session = scoped_session(session_factory)
        self.db_ready.set()

    def _close_connection(self):
        """Close the connection."""
        global Session  # pylint: disable=global-statement
        self.engine.dispose()
        self.engine = None
        Session = None

    def _setup_run(self):
        """Log the start of the current run."""
        recorder_runs = get_model('RecorderRuns')
        for run in query('RecorderRuns').filter_by(end=None):
            run.closed_incorrect = True
            run.end = self.recording_start
            _LOGGER.warning("Ended unfinished session (id=%s from %s)",
                            run.run_id, run.start)
            Session.add(run)

            _LOGGER.warning("Found unfinished sessions")

        self._run = recorder_runs(
            start=self.recording_start,
            created=dt_util.utcnow()
        )
        self._commit(self._run)

    def _close_run(self):
        """Save end time for current run."""
        self._run.end = dt_util.utcnow()
        self._commit(self._run)
        self._run = None

    def _purge_old_data(self):
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

        if self._commit(_purge_states):
            _LOGGER.info("Purged states created before %s", purge_before)

        def _purge_events(session):
            deleted_rows = session.query(Events) \
                                  .filter((Events.created < purge_before)) \
                                  .delete(synchronize_session=False)
            _LOGGER.debug("Deleted %s events", deleted_rows)

        if self._commit(_purge_events):
            _LOGGER.info("Purged events created before %s", purge_before)

        Session.expire_all()

        # Execute sqlite vacuum command to free up space on disk
        if self.engine.driver == 'sqlite':
            _LOGGER.info("Vacuuming SQLite to free space")
            self.engine.execute("VACUUM")

    @staticmethod
    def _commit(work):
        """Commit & retry work: Either a model or in a function."""
        import sqlalchemy.exc
        session = Session()
        for _ in range(0, RETRIES):
            try:
                if callable(work):
                    work(session)
                else:
                    session.add(work)
                session.commit()
                return True
            except sqlalchemy.exc.OperationalError as e:
                log_error(e, retry_wait=QUERY_RETRY_WAIT, rollback=True)
        return False


def _verify_instance() -> None:
    """Throw error if recorder not initialized."""
    if _INSTANCE is None:
        raise RuntimeError("Recorder not initialized.")
    _INSTANCE.block_till_db_ready()

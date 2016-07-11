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
from datetime import timedelta

import voluptuous as vol

import homeassistant.util.dt as dt_util
from homeassistant.const import (EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED,
                                 EVENT_TIME_CHANGED, MATCH_ALL)
from homeassistant.helpers.event import track_point_in_utc_time

DOMAIN = "recorder"

REQUIREMENTS = ['sqlalchemy==1.0.14']

DEFAULT_URL = "sqlite:///{hass_config_path}"
DEFAULT_DB_FILE = "home-assistant_v2.db"

CONF_DB_URL = "db_url"
CONF_PURGE_DAYS = "purge_days"

RETRIES = 3
CONNECT_RETRY_WAIT = 10
QUERY_RETRY_WAIT = 0.1

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_PURGE_DAYS): vol.All(vol.Coerce(int),
                                               vol.Range(min=1)),
        vol.Optional(CONF_DB_URL): vol.Url(''),
    })
}, extra=vol.ALLOW_EXTRA)

_INSTANCE = None
_LOGGER = logging.getLogger(__name__)

# These classes will be populated during setup()
# pylint: disable=invalid-name
Session = None


def execute(q):
    """Query the database and convert the objects to HA native form.

    This method also retries a few times in the case of stale connections.
    """
    import sqlalchemy.exc
    for _ in range(0, RETRIES):
        try:
            return [
                row for row in
                (row.to_native() for row in q)
                if row is not None]
        except sqlalchemy.exc.SQLAlchemyError as e:
            log_error(e, retry_wait=QUERY_RETRY_WAIT, rollback=True)
    return []


def run_information(point_in_time=None):
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


def setup(hass, config):
    """Setup the recorder."""
    # pylint: disable=global-statement
    # pylint: disable=too-many-locals
    global _INSTANCE
    purge_days = config.get(DOMAIN, {}).get(CONF_PURGE_DAYS)

    db_url = config.get(DOMAIN, {}).get(CONF_DB_URL, None)
    if not db_url:
        db_url = DEFAULT_URL.format(
            hass_config_path=hass.config.path(DEFAULT_DB_FILE))

    _INSTANCE = Recorder(hass, purge_days=purge_days, uri=db_url)

    return True


def query(model_name, *args):
    """Helper to return a query handle."""
    if isinstance(model_name, str):
        return Session().query(get_model(model_name), *args)
    return Session().query(model_name, *args)


def get_model(model_name):
    """Get a model class."""
    from homeassistant.components.recorder import models

    return getattr(models, model_name)


def log_error(e, retry_wait=0, rollback=True,
              message="Error during query: %s"):
    """Log about SQLAlchemy errors in a sane manner."""
    import sqlalchemy.exc
    if not isinstance(e, sqlalchemy.exc.OperationalError):
        _LOGGER.exception(e)
    else:
        _LOGGER.error(message, str(e))
    if rollback:
        Session().rollback()
    if retry_wait:
        _LOGGER.info("Retrying failed query in %s seconds", QUERY_RETRY_WAIT)
        time.sleep(retry_wait)


class Recorder(threading.Thread):
    """A threaded recorder class."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass, purge_days, uri):
        """Initialize the recorder."""
        threading.Thread.__init__(self)

        self.hass = hass
        self.purge_days = purge_days
        self.queue = queue.Queue()
        self.quit_object = object()
        self.recording_start = dt_util.utcnow()
        self.db_url = uri
        self.db_ready = threading.Event()
        self.engine = None
        self._run = None

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

        global _INSTANCE

        while True:
            try:
                self._setup_connection()
                self._setup_run()
                break
            except sqlalchemy.exc.SQLAlchemyError as e:
                log_error(e, retry_wait=CONNECT_RETRY_WAIT, rollback=False,
                          message="Error during connection setup: %s")

        if self.purge_days is not None:
            track_point_in_utc_time(self.hass,
                                    lambda now: self._purge_old_data(),
                                    dt_util.utcnow() + timedelta(minutes=5))

        while True:
            event = self.queue.get()

            if event == self.quit_object:
                self._close_run()
                self._close_connection()
                _INSTANCE = None
                self.queue.task_done()
                return

            elif event.event_type == EVENT_TIME_CHANGED:
                self.queue.task_done()
                continue

            session = Session()
            dbevent = Events.from_event(event)
            session.add(dbevent)

            for _ in range(0, RETRIES):
                try:
                    session.commit()
                    break
                except sqlalchemy.exc.OperationalError as e:
                    log_error(e, retry_wait=QUERY_RETRY_WAIT,
                              rollback=True)

            if event.event_type != EVENT_STATE_CHANGED:
                self.queue.task_done()
                continue

            session = Session()
            dbstate = States.from_event(event)

            for _ in range(0, RETRIES):
                try:
                    dbstate.event_id = dbevent.event_id
                    session.add(dbstate)
                    session.commit()
                    break
                except sqlalchemy.exc.OperationalError as e:
                    log_error(e, retry_wait=QUERY_RETRY_WAIT,
                              rollback=True)

            self.queue.task_done()

    def event_listener(self, event):
        """Listen for new events and put them in the process queue."""
        self.queue.put(event)

    def shutdown(self, event):
        """Tell the recorder to shut down."""
        self.queue.put(self.quit_object)
        self.queue.join()

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()

    def block_till_db_ready(self):
        """Block until the database session is ready."""
        self.db_ready.wait()

    def _setup_connection(self):
        """Ensure database is ready to fly."""
        # pylint: disable=global-statement
        global Session

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
        global Session
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
            Session().add(run)

            _LOGGER.warning("Found unfinished sessions")

        self._run = recorder_runs(
            start=self.recording_start,
            created=dt_util.utcnow()
        )
        session = Session()
        session.add(self._run)
        session.commit()

    def _close_run(self):
        """Save end time for current run."""
        self._run.end = dt_util.utcnow()
        session = Session()
        session.add(self._run)
        session.commit()
        self._run = None

    def _purge_old_data(self):
        """Purge events and states older than purge_days ago."""
        from homeassistant.components.recorder.models import Events, States

        if not self.purge_days or self.purge_days < 1:
            _LOGGER.debug("purge_days set to %s, will not purge any old data.",
                          self.purge_days)
            return

        purge_before = dt_util.utcnow() - timedelta(days=self.purge_days)

        _LOGGER.info("Purging events created before %s", purge_before)
        deleted_rows = Session().query(Events).filter(
            (Events.created < purge_before)).delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s events", deleted_rows)

        _LOGGER.info("Purging states created before %s", purge_before)
        deleted_rows = Session().query(States).filter(
            (States.created < purge_before)).delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s states", deleted_rows)

        Session().commit()
        Session().expire_all()

        # Execute sqlite vacuum command to free up space on disk
        if self.engine.driver == 'sqlite':
            _LOGGER.info("Vacuuming SQLite to free space")
            self.engine.execute("VACUUM")


def _verify_instance():
    """Throw error if recorder not initialized."""
    if _INSTANCE is None:
        raise RuntimeError("Recorder not initialized.")

"""
Support for recording details.

Component that records all events and state changes. Allows other components
to query this database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/recorder/
"""
import atexit
import json
import logging
import queue
import sqlite3
import threading
from datetime import date, datetime, timedelta
import voluptuous as vol

import homeassistant.util.dt as dt_util
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED, MATCH_ALL)
from homeassistant.core import Event, EventOrigin, State
from homeassistant.remote import JSONEncoder
from homeassistant.helpers.event import track_point_in_utc_time

DOMAIN = "recorder"

DB_FILE = 'home-assistant.db'

RETURN_ROWCOUNT = "rowcount"
RETURN_LASTROWID = "lastrowid"
RETURN_ONE_ROW = "one_row"

CONF_PURGE_DAYS = "purge_days"
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_PURGE_DAYS): vol.All(vol.Coerce(int),
                                               vol.Range(min=1)),
    })
}, extra=vol.ALLOW_EXTRA)


_INSTANCE = None
_LOGGER = logging.getLogger(__name__)


def query(sql_query, arguments=None):
    """Query the database."""
    _verify_instance()

    return _INSTANCE.query(sql_query, arguments)


def query_states(state_query, arguments=None):
    """Query the database and return a list of states."""
    return [
        row for row in
        (row_to_state(row) for row in query(state_query, arguments))
        if row is not None]


def query_events(event_query, arguments=None):
    """Query the database and return a list of states."""
    return [
        row for row in
        (row_to_event(row) for row in query(event_query, arguments))
        if row is not None]


def row_to_state(row):
    """Convert a database row to a state."""
    try:
        return State(
            row[1], row[2], json.loads(row[3]),
            dt_util.utc_from_timestamp(row[4]),
            dt_util.utc_from_timestamp(row[5]))
    except ValueError:
        # When json.loads fails
        _LOGGER.exception("Error converting row to state: %s", row)
        return None


def row_to_event(row):
    """Convert a databse row to an event."""
    try:
        return Event(row[1], json.loads(row[2]), EventOrigin(row[3]),
                     dt_util.utc_from_timestamp(row[5]))
    except ValueError:
        # When json.loads fails
        _LOGGER.exception("Error converting row to event: %s", row)
        return None


def run_information(point_in_time=None):
    """Return information about current run.

    There is also the run that covers point_in_time.
    """
    _verify_instance()

    if point_in_time is None or point_in_time > _INSTANCE.recording_start:
        return RecorderRun()

    run = _INSTANCE.query(
        "SELECT * FROM recorder_runs WHERE start<? AND END>?",
        (point_in_time, point_in_time), return_value=RETURN_ONE_ROW)

    return RecorderRun(run) if run else None


def setup(hass, config):
    """Setup the recorder."""
    # pylint: disable=global-statement
    global _INSTANCE
    purge_days = config.get(DOMAIN, {}).get(CONF_PURGE_DAYS)
    _INSTANCE = Recorder(hass, purge_days=purge_days)

    return True


class RecorderRun(object):
    """Representation of a recorder run."""

    def __init__(self, row=None):
        """Initialize the recorder run."""
        self.end = None

        if row is None:
            self.start = _INSTANCE.recording_start
            self.closed_incorrect = False
        else:
            self.start = dt_util.utc_from_timestamp(row[1])

            if row[2] is not None:
                self.end = dt_util.utc_from_timestamp(row[2])

            self.closed_incorrect = bool(row[3])

    def entity_ids(self, point_in_time=None):
        """Return the entity ids that existed in this run.

        Specify point_in_time if you want to know which existed at that point
        in time inside the run.
        """
        where = self.where_after_start_run
        where_data = []

        if point_in_time is not None or self.end is not None:
            where += "AND created < ? "
            where_data.append(point_in_time or self.end)

        return [row[0] for row in query(
            "SELECT entity_id FROM states WHERE {}"
            "GROUP BY entity_id".format(where), where_data)]

    @property
    def where_after_start_run(self):
        """Return SQL WHERE clause.

        Selection of the rows created after the start of the run.
        """
        return "created >= {} ".format(_adapt_datetime(self.start))

    @property
    def where_limit_to_run(self):
        """Return a SQL WHERE clause.

        For limiting the results to this run.
        """
        where = self.where_after_start_run

        if self.end is not None:
            where += "AND created < {} ".format(_adapt_datetime(self.end))

        return where


class Recorder(threading.Thread):
    """A threaded recorder class."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass, purge_days):
        """Initialize the recorder."""
        threading.Thread.__init__(self)

        self.hass = hass
        self.purge_days = purge_days
        self.conn = None
        self.queue = queue.Queue()
        self.quit_object = object()
        self.lock = threading.Lock()
        self.recording_start = dt_util.utcnow()
        self.utc_offset = dt_util.now().utcoffset().total_seconds()
        self.db_path = self.hass.config.path(DB_FILE)

        def start_recording(event):
            """Start recording."""
            self.start()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_recording)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        hass.bus.listen(MATCH_ALL, self.event_listener)

    def run(self):
        """Start processing events to save."""
        self._setup_connection()
        self._setup_run()
        if self.purge_days is not None:
            track_point_in_utc_time(self.hass,
                                    lambda now: self._purge_old_data(),
                                    dt_util.utcnow() + timedelta(minutes=5))

        while True:
            event = self.queue.get()

            if event == self.quit_object:
                self._close_run()
                self._close_connection()
                self.queue.task_done()
                return

            elif event.event_type == EVENT_TIME_CHANGED:
                self.queue.task_done()
                continue

            event_id = self.record_event(event)

            if event.event_type == EVENT_STATE_CHANGED:
                self.record_state(
                    event.data['entity_id'], event.data.get('new_state'),
                    event_id)

            self.queue.task_done()

    def event_listener(self, event):
        """Listen for new events and put them in the process queue."""
        self.queue.put(event)

    def shutdown(self, event):
        """Tell the recorder to shut down."""
        self.queue.put(self.quit_object)
        self.block_till_done()

    def record_state(self, entity_id, state, event_id):
        """Save a state to the database."""
        now = dt_util.utcnow()

        # State got deleted
        if state is None:
            state_state = ''
            state_domain = ''
            state_attr = '{}'
            last_changed = last_updated = now
        else:
            state_domain = state.domain
            state_state = state.state
            state_attr = json.dumps(dict(state.attributes))
            last_changed = state.last_changed
            last_updated = state.last_updated

        info = (
            entity_id, state_domain, state_state, state_attr,
            last_changed, last_updated,
            now, self.utc_offset, event_id)

        self.query(
            """
            INSERT INTO states (
            entity_id, domain, state, attributes, last_changed, last_updated,
            created, utc_offset, event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            info)

    def record_event(self, event):
        """Save an event to the database."""
        info = (
            event.event_type, json.dumps(event.data, cls=JSONEncoder),
            str(event.origin), dt_util.utcnow(), event.time_fired,
            self.utc_offset
        )

        return self.query(
            "INSERT INTO events ("
            "event_type, event_data, origin, created, time_fired, utc_offset"
            ") VALUES (?, ?, ?, ?, ?, ?)", info, RETURN_LASTROWID)

    def query(self, sql_query, data=None, return_value=None):
        """Query the database."""
        try:
            with self.conn, self.lock:
                _LOGGER.debug("Running query %s", sql_query)

                cur = self.conn.cursor()

                if data is not None:
                    cur.execute(sql_query, data)
                else:
                    cur.execute(sql_query)

                if return_value == RETURN_ROWCOUNT:
                    return cur.rowcount
                elif return_value == RETURN_LASTROWID:
                    return cur.lastrowid
                elif return_value == RETURN_ONE_ROW:
                    return cur.fetchone()
                else:
                    return cur.fetchall()

        except (sqlite3.IntegrityError, sqlite3.OperationalError,
                sqlite3.ProgrammingError):
            _LOGGER.exception(
                "Error querying the database using: %s", sql_query)
            return []

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()

    def _setup_connection(self):
        """Ensure database is ready to fly."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Make sure the database is closed whenever Python exits
        # without the STOP event being fired.
        atexit.register(self._close_connection)

        # Have datetime objects be saved as integers.
        sqlite3.register_adapter(date, _adapt_datetime)
        sqlite3.register_adapter(datetime, _adapt_datetime)

        # Validate we are on the correct schema or that we have to migrate.
        cur = self.conn.cursor()

        def save_migration(migration_id):
            """Save and commit a migration to the database."""
            cur.execute('INSERT INTO schema_version VALUES (?, ?)',
                        (migration_id, dt_util.utcnow()))
            self.conn.commit()
            _LOGGER.info("Database migrated to version %d", migration_id)

        try:
            cur.execute('SELECT max(migration_id) FROM schema_version;')
            migration_id = cur.fetchone()[0] or 0

        except sqlite3.OperationalError:
            # The table does not exist.
            cur.execute('CREATE TABLE schema_version ('
                        'migration_id integer primary key, performed integer)')
            migration_id = 0

        if migration_id < 1:
            cur.execute("""
                CREATE TABLE recorder_runs (
                    run_id integer primary key,
                    start integer,
                    end integer,
                    closed_incorrect integer default 0,
                    created integer)
            """)

            cur.execute("""
                CREATE TABLE events (
                    event_id integer primary key,
                    event_type text,
                    event_data text,
                    origin text,
                    created integer)
            """)
            cur.execute(
                'CREATE INDEX events__event_type ON events(event_type)')

            cur.execute("""
                CREATE TABLE states (
                    state_id integer primary key,
                    entity_id text,
                    state text,
                    attributes text,
                    last_changed integer,
                    last_updated integer,
                    created integer)
            """)
            cur.execute('CREATE INDEX states__entity_id ON states(entity_id)')

            save_migration(1)

        if migration_id < 2:
            cur.execute("""
                ALTER TABLE events
                ADD COLUMN time_fired integer
            """)

            cur.execute('UPDATE events SET time_fired=created')

            save_migration(2)

        if migration_id < 3:
            utc_offset = self.utc_offset

            cur.execute("""
                ALTER TABLE recorder_runs
                ADD COLUMN utc_offset integer
            """)

            cur.execute("""
                ALTER TABLE events
                ADD COLUMN utc_offset integer
            """)

            cur.execute("""
                ALTER TABLE states
                ADD COLUMN utc_offset integer
            """)

            cur.execute("UPDATE recorder_runs SET utc_offset=?", [utc_offset])
            cur.execute("UPDATE events SET utc_offset=?", [utc_offset])
            cur.execute("UPDATE states SET utc_offset=?", [utc_offset])

            save_migration(3)

        if migration_id < 4:
            # We had a bug where we did not save utc offset for recorder runs.
            cur.execute(
                """UPDATE recorder_runs SET utc_offset=?
                   WHERE utc_offset IS NULL""", [self.utc_offset])

            cur.execute("""
                ALTER TABLE states
                ADD COLUMN event_id integer
            """)

            save_migration(4)

        if migration_id < 5:
            # Add domain so that thermostat graphs look right.
            try:
                cur.execute("""
                    ALTER TABLE states
                    ADD COLUMN domain text
                """)
            except sqlite3.OperationalError:
                # We had a bug in this migration for a while on dev.
                # Without this, dev-users will have to throw away their db.
                pass

            # TravisCI has Python compiled against an old version of SQLite3
            # which misses the instr method.
            self.conn.create_function(
                "instr", 2,
                lambda string, substring: string.find(substring) + 1)

            # Populate domain with defaults.
            cur.execute("""
                UPDATE states
                set domain=substr(entity_id, 0, instr(entity_id, '.'))
            """)

            # Add indexes we are going to use a lot on selects.
            cur.execute("""
                CREATE INDEX states__state_changes ON
                states (last_changed, last_updated, entity_id)""")
            cur.execute("""
                CREATE INDEX states__significant_changes ON
                states (domain, last_updated, entity_id)""")
            save_migration(5)

    def _close_connection(self):
        """Close connection to the database."""
        _LOGGER.info("Closing database")
        atexit.unregister(self._close_connection)
        self.conn.close()

    def _setup_run(self):
        """Log the start of the current run."""
        if self.query("""UPDATE recorder_runs SET end=?, closed_incorrect=1
                      WHERE end IS NULL""", (self.recording_start, ),
                      return_value=RETURN_ROWCOUNT):

            _LOGGER.warning("Found unfinished sessions")

        self.query(
            """INSERT INTO recorder_runs (start, created, utc_offset)
               VALUES (?, ?, ?)""",
            (self.recording_start, dt_util.utcnow(), self.utc_offset))

    def _close_run(self):
        """Save end time for current run."""
        self.query(
            "UPDATE recorder_runs SET end=? WHERE start=?",
            (dt_util.utcnow(), self.recording_start))

    def _purge_old_data(self):
        """Purge events and states older than purge_days ago."""
        if not self.purge_days or self.purge_days < 1:
            _LOGGER.debug("purge_days set to %s, will not purge any old data.",
                          self.purge_days)
            return

        purge_before = dt_util.utcnow() - timedelta(days=self.purge_days)

        _LOGGER.info("Purging events created before %s", purge_before)
        deleted_rows = self.query(
            sql_query="DELETE FROM events WHERE created < ?;",
            data=(int(purge_before.timestamp()),),
            return_value=RETURN_ROWCOUNT)
        _LOGGER.debug("Deleted %s events", deleted_rows)

        _LOGGER.info("Purging states created before %s", purge_before)
        deleted_rows = self.query(
            sql_query="DELETE FROM states WHERE created < ?;",
            data=(int(purge_before.timestamp()),),
            return_value=RETURN_ROWCOUNT)
        _LOGGER.debug("Deleted %s states", deleted_rows)

        # Execute sqlite vacuum command to free up space on disk
        self.query("VACUUM;")


def _adapt_datetime(datetimestamp):
    """Turn a datetime into an integer for in the DB."""
    return dt_util.as_utc(datetimestamp).timestamp()


def _verify_instance():
    """Throw error if recorder not initialized."""
    if _INSTANCE is None:
        raise RuntimeError("Recorder not initialized.")

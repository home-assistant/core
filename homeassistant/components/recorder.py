import logging
import threading
import queue
import sqlite3
from datetime import datetime
import time
import json

from homeassistant import Event, EventOrigin, State
from homeassistant.remote import JSONEncoder
from homeassistant.const import (
    MATCH_ALL, EVENT_TIME_CHANGED, EVENT_STATE_CHANGED,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

DOMAIN = "recorder"
DEPENDENCIES = []

DB_FILE = 'home-assistant.db'
_INSTANCE = None
_LOGGER = logging.getLogger(__name__)


def query(query, arguments):
    """ Query the database. """
    verify_instance()

    return _INSTANCE.query(query, arguments)


def query_states(state_query, arguments):
    """ Query the database and return a list of states. """
    return filter(None, (row_to_state(row) for row in query(state_query, arguments)))


def query_events(event_query, arguments):
    """ Query the database and return a list of states. """
    return filter(None, (row_to_event(row) for row in query(event_query, arguments)))


def row_to_state(row):
    """ Convert a databsae row to a state. """
    try:
        return State(
            row[1], row[2], json.loads(row[3]), datetime.fromtimestamp(row[4]))
    except ValueError:
        # When json.loads fails
        return None


def row_to_event(row):
    """ Convert a databse row to an event. """
    try:
        return Event(row[1], json.loads(row[2]), EventOrigin[row[3].lower()])
    except ValueError:
        # When json.oads fails
        return None


def verify_instance():
    """ Raise error if recorder is not setup. """
    if _INSTANCE is None:
        raise RuntimeError("Recorder not initialized.")


def setup(hass, config):
    """ Setup the recorder. """
    global _INSTANCE

    _INSTANCE = Recorder(hass)

    return True


class Recorder(threading.Thread):
    """
    Threaded recorder
    """
    def __init__(self, hass):
        threading.Thread.__init__(self)

        self.hass = hass
        self.conn = None
        self.queue = queue.Queue()
        self.quit_object = object()
        self.lock = threading.Lock()

        def start_recording(event):
            """ Start recording. """
            self.start()
            hass.states.set('paulus.held', 'juist', {'nou en': 'bier'})

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_recording)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        hass.bus.listen(MATCH_ALL, self.event_listener)

    def run(self):
        """ Start processing events to save. """
        self._setup_connection()

        while True:
            event = self.queue.get()

            if event == self.quit_object:
                self._close_connection()
                return

            elif event.event_type == EVENT_TIME_CHANGED:
                continue

            elif event.event_type == EVENT_STATE_CHANGED:
                self.record_state(
                    event.data['entity_id'], event.data.get('new_state'))

            self.record_event(event)

    def event_listener(self, event):
        """ Listens for new events on the EventBus and puts them
            in the process queue. """
        self.queue.put(event)

    def shutdown(self, event):
        """ Tells the recorder to shut down. """
        self.queue.put(self.quit_object)

    def record_state(self, entity_id, state):
        """ Save a state to the database. """
        now = datetime.now()

        if state is None:
            info = (entity_id, '', "{}", now, now, now)
        else:
            info = (
                entity_id, state.state, json.dumps(state.attributes),
                state.last_changed, state.last_updated, now)

        self.query(
            "insert into states ("
            "entity_id, state, attributes, last_changed, last_updated,"
            "created) values (?, ?, ?, ?, ?, ?)", info)

    def record_event(self, event):
        """ Save an event to the database. """
        info = (
            event.event_type, json.dumps(event.data, cls=JSONEncoder),
            str(event.origin), datetime.now()
        )

        self.query(
            "insert into events ("
            "event_type, event_data, origin, created"
            ") values (?, ?, ?, ?)", info)

    def query(self, query, data=None):
        """ Query the database. """
        try:
            with self.conn, self.lock:
                cur = self.conn.cursor()

                if data is not None:
                    cur.execute(query, data)
                else:
                    cur.execute(query)

                return cur.fetchall()

        except sqlite3.IntegrityError:
            _LOGGER.exception("Error querying the database using: %s", query)
            return []

    def _setup_connection(self):
        """ Ensure database is ready to fly. """
        db_path = self.hass.get_config_path(DB_FILE)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)

        # Have datetime objects be saved as integers
        sqlite3.register_adapter(datetime, adapt_datetime)

        # Validate we are on the correct schema or that we have to migrate
        c = self.conn.cursor()

        def save_migration(migration_id):
            c.execute('INSERT INTO schema_version VALUES (?, ?)',
                      (migration_id, datetime.now()))
            self.conn.commit()
            _LOGGER.info("Database migrated to version %d", migration_id)

        try:
            c.execute('SELECT max(migration_id) FROM schema_version;')
            migration_id = c.fetchone()[0] or 0

        except sqlite3.OperationalError:
            # The table does not exist
            c.execute('CREATE TABLE schema_version '
                      '(migration_id integer primary key, performed integer)')
            migration_id = 0

        if migration_id < 1:
            c.execute(
                'CREATE TABLE events (event_id integer primary key, '
                'event_type text, event_data text, origin text, '
                'created integer)')
            c.execute('CREATE INDEX events__event_type ON events(event_type)')

            c.execute(
                'CREATE TABLE states (state_id integer primary key, '
                'entity_id text, state text, attributes text, '
                'last_changed integer, last_updated integer, created integer)')
            c.execute('CREATE INDEX states__entity_id ON states(entity_id)')

            save_migration(1)

    def _close_connection(self):
        _LOGGER.info("Closing database")
        self.conn.close()


# Setup datetime to save as a integer
def adapt_datetime(ts):
    return time.mktime(ts.timetuple())

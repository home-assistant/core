"""
A component which allows you to send data to an Influx database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/influxdb/
"""
import logging
import re
import queue
import threading
import time

import requests.exceptions
import voluptuous as vol

from homeassistant.const import (
    CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_HOST, CONF_INCLUDE,
    CONF_PASSWORD, CONF_PORT, CONF_SSL, CONF_USERNAME, CONF_VERIFY_SSL,
    EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE,
    STATE_UNKNOWN)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_values import EntityValues

REQUIREMENTS = ['influxdb==5.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_DB_NAME = 'database'
CONF_TAGS = 'tags'
CONF_DEFAULT_MEASUREMENT = 'default_measurement'
CONF_OVERRIDE_MEASUREMENT = 'override_measurement'
CONF_TAGS_ATTRIBUTES = 'tags_attributes'
CONF_COMPONENT_CONFIG = 'component_config'
CONF_COMPONENT_CONFIG_GLOB = 'component_config_glob'
CONF_COMPONENT_CONFIG_DOMAIN = 'component_config_domain'
CONF_RETRY_COUNT = 'max_retries'
CONF_RETRY_QUEUE = 'retry_queue_limit'

DEFAULT_DATABASE = 'home_assistant'
DEFAULT_VERIFY_SSL = True
DOMAIN = 'influxdb'

TIMEOUT = 5
RETRY_DELAY = 20
QUEUE_BACKLOG_SECONDS = 10

COMPONENT_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.deprecated(CONF_RETRY_QUEUE), vol.Schema({
        vol.Optional(CONF_HOST): cv.string,
        vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
        vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
        vol.Optional(CONF_EXCLUDE, default={}): vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        }),
        vol.Optional(CONF_INCLUDE, default={}): vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        }),
        vol.Optional(CONF_DB_NAME, default=DEFAULT_DATABASE): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL): cv.boolean,
        vol.Optional(CONF_RETRY_COUNT, default=0): cv.positive_int,
        vol.Optional(CONF_RETRY_QUEUE, default=20): cv.positive_int,
        vol.Optional(CONF_DEFAULT_MEASUREMENT): cv.string,
        vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string,
        vol.Optional(CONF_TAGS, default={}):
            vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_TAGS_ATTRIBUTES, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_COMPONENT_CONFIG, default={}):
            vol.Schema({cv.entity_id: COMPONENT_CONFIG_SCHEMA_ENTRY}),
        vol.Optional(CONF_COMPONENT_CONFIG_GLOB, default={}):
            vol.Schema({cv.string: COMPONENT_CONFIG_SCHEMA_ENTRY}),
        vol.Optional(CONF_COMPONENT_CONFIG_DOMAIN, default={}):
            vol.Schema({cv.string: COMPONENT_CONFIG_SCHEMA_ENTRY}),
    })),
}, extra=vol.ALLOW_EXTRA)

RE_DIGIT_TAIL = re.compile(r'^[^\.]*\d+\.?\d+[^\.]*$')
RE_DECIMAL = re.compile(r'[^\d.]+')


def setup(hass, config):
    """Set up the InfluxDB component."""
    from influxdb import InfluxDBClient, exceptions

    conf = config[DOMAIN]

    kwargs = {
        'database': conf[CONF_DB_NAME],
        'verify_ssl': conf[CONF_VERIFY_SSL],
        'timeout': TIMEOUT
    }

    if CONF_HOST in conf:
        kwargs['host'] = conf[CONF_HOST]

    if CONF_PORT in conf:
        kwargs['port'] = conf[CONF_PORT]

    if CONF_USERNAME in conf:
        kwargs['username'] = conf[CONF_USERNAME]

    if CONF_PASSWORD in conf:
        kwargs['password'] = conf[CONF_PASSWORD]

    if CONF_SSL in conf:
        kwargs['ssl'] = conf[CONF_SSL]

    include = conf.get(CONF_INCLUDE, {})
    exclude = conf.get(CONF_EXCLUDE, {})
    whitelist_e = set(include.get(CONF_ENTITIES, []))
    whitelist_d = set(include.get(CONF_DOMAINS, []))
    blacklist_e = set(exclude.get(CONF_ENTITIES, []))
    blacklist_d = set(exclude.get(CONF_DOMAINS, []))
    tags = conf.get(CONF_TAGS)
    tags_attributes = conf.get(CONF_TAGS_ATTRIBUTES)
    default_measurement = conf.get(CONF_DEFAULT_MEASUREMENT)
    override_measurement = conf.get(CONF_OVERRIDE_MEASUREMENT)
    component_config = EntityValues(
        conf[CONF_COMPONENT_CONFIG],
        conf[CONF_COMPONENT_CONFIG_DOMAIN],
        conf[CONF_COMPONENT_CONFIG_GLOB])
    max_tries = conf.get(CONF_RETRY_COUNT)

    try:
        influx = InfluxDBClient(**kwargs)
        influx.query("SHOW SERIES LIMIT 1;", database=conf[CONF_DB_NAME])
    except (exceptions.InfluxDBClientError,
            requests.exceptions.ConnectionError) as exc:
        _LOGGER.error("Database host is not accessible due to '%s', please "
                      "check your entries in the configuration file (host, "
                      "port, etc.) and verify that the database exists and is "
                      "READ/WRITE", exc)
        return False

    def influx_handle_event(event):
        """Send an event to Influx."""
        state = event.data.get('new_state')
        if state is None or state.state in (
                STATE_UNKNOWN, '', STATE_UNAVAILABLE) or \
                state.entity_id in blacklist_e or state.domain in blacklist_d:
            return True

        try:
            if (whitelist_e and state.entity_id not in whitelist_e) or \
                    (whitelist_d and state.domain not in whitelist_d):
                return True

            _include_state = _include_value = False

            _state_as_value = float(state.state)
            _include_value = True
        except ValueError:
            try:
                _state_as_value = float(state_helper.state_as_number(state))
                _include_state = _include_value = True
            except ValueError:
                _include_state = True

        include_uom = True
        measurement = component_config.get(state.entity_id).get(
            CONF_OVERRIDE_MEASUREMENT)
        if measurement in (None, ''):
            if override_measurement:
                measurement = override_measurement
            else:
                measurement = state.attributes.get('unit_of_measurement')
                if measurement in (None, ''):
                    if default_measurement:
                        measurement = default_measurement
                    else:
                        measurement = state.entity_id
                else:
                    include_uom = False

        json_body = [
            {
                'measurement': measurement,
                'tags': {
                    'domain': state.domain,
                    'entity_id': state.object_id,
                },
                'time': event.time_fired,
                'fields': {
                }
            }
        ]
        if _include_state:
            json_body[0]['fields']['state'] = state.state
        if _include_value:
            json_body[0]['fields']['value'] = _state_as_value

        for key, value in state.attributes.items():
            if key in tags_attributes:
                json_body[0]['tags'][key] = value
            elif key != 'unit_of_measurement' or include_uom:
                # If the key is already in fields
                if key in json_body[0]['fields']:
                    key = key + "_"
                # Prevent column data errors in influxDB.
                # For each value we try to cast it as float
                # But if we can not do it we store the value
                # as string add "_str" postfix to the field key
                try:
                    json_body[0]['fields'][key] = float(value)
                except (ValueError, TypeError):
                    new_key = "{}_str".format(key)
                    new_value = str(value)
                    json_body[0]['fields'][new_key] = new_value

                    if RE_DIGIT_TAIL.match(new_value):
                        json_body[0]['fields'][key] = float(
                            RE_DECIMAL.sub('', new_value))

        json_body[0]['tags'].update(tags)

        try:
            influx.write_points(json_body)
            return True
        except (exceptions.InfluxDBClientError, IOError):
            return False

    instance = hass.data[DOMAIN] = InfluxThread(
        hass, influx_handle_event, max_tries)
    instance.start()

    def shutdown(event):
        """Shut down the thread."""
        instance.queue.put(None)
        instance.join()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class InfluxThread(threading.Thread):
    """A threaded event handler class."""

    def __init__(self, hass, event_handler, max_tries):
        """Initialize the listener."""
        threading.Thread.__init__(self, name='InfluxDB')
        self.queue = queue.Queue()
        self.event_handler = event_handler
        self.max_tries = max_tries
        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)

    def _event_listener(self, event):
        """Listen for new messages on the bus and queue them for Influx."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    def run(self):
        """Process incoming events."""
        queue_seconds = QUEUE_BACKLOG_SECONDS + self.max_tries*RETRY_DELAY

        write_error = False
        dropped = False

        while True:
            item = self.queue.get()

            if item is None:
                self.queue.task_done()
                return

            timestamp, event = item
            age = time.monotonic() - timestamp

            if age < queue_seconds:
                for retry in range(self.max_tries+1):
                    if self.event_handler(event):
                        if write_error:
                            _LOGGER.error("Resumed writing to InfluxDB")
                            write_error = False
                        dropped = False
                        break
                    elif retry < self.max_tries:
                        time.sleep(RETRY_DELAY)
                    elif not write_error:
                        _LOGGER.error("Error writing to InfluxDB")
                        write_error = True
            elif not dropped:
                _LOGGER.warning("Dropping old events to catch up")
                dropped = True

            self.queue.task_done()

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()

"""
A component which allows you to send data to an Influx database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/influxdb/
"""
from datetime import timedelta
from functools import wraps, partial
import logging
import re

import requests.exceptions
import voluptuous as vol

from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN, CONF_HOST,
    CONF_PORT, CONF_SSL, CONF_VERIFY_SSL, CONF_USERNAME, CONF_PASSWORD,
    CONF_EXCLUDE, CONF_INCLUDE, CONF_DOMAINS, CONF_ENTITIES)
from homeassistant.helpers import state as state_helper
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.util import utcnow
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['influxdb==4.1.1']

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

COMPONENT_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
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
    }),
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
    queue_limit = conf.get(CONF_RETRY_QUEUE)

    try:
        influx = InfluxDBClient(**kwargs)
        influx.query("SHOW SERIES LIMIT 1;", database=conf[CONF_DB_NAME])
    except (exceptions.InfluxDBClientError,
            requests.exceptions.ConnectionError) as exc:
        _LOGGER.error("Database host is not accessible due to '%s', please "
                      "check your entries in the configuration file (host, "
                      "port, etc.) and verify that the database exists and is "
                      "READ/WRITE.", exc)
        return False

    def influx_event_listener(event):
        """Listen for new messages on the bus and sends them to Influx."""
        state = event.data.get('new_state')
        if state is None or state.state in (
                STATE_UNKNOWN, '', STATE_UNAVAILABLE) or \
                state.entity_id in blacklist_e or \
                state.domain in blacklist_d:
            return

        try:
            if (whitelist_e and state.entity_id not in whitelist_e) or \
                    (whitelist_d and state.domain not in whitelist_d):
                return

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

        _write_data(json_body)

    @RetryOnError(hass, retry_limit=max_tries, retry_delay=20,
                  queue_limit=queue_limit)
    def _write_data(json_body):
        try:
            influx.write_points(json_body)
        except exceptions.InfluxDBClientError:
            _LOGGER.exception("Error saving event %s to InfluxDB", json_body)

    hass.bus.listen(EVENT_STATE_CHANGED, influx_event_listener)

    return True


class RetryOnError(object):
    """A class for retrying a failed task a certain amount of tries.

    This method decorator makes a method retrying on errors. If there was an
    uncaught exception, it schedules another try to execute the task after a
    retry delay. It does this up to the maximum number of retries.

    It can be used for all probable "self-healing" problems like network
    outages. The task will be rescheduled using HAs scheduling mechanism.

    It takes a Hass instance, a maximum number of retries and a retry delay
    in seconds as arguments.

    The queue limit defines the maximum number of calls that are allowed to
    be queued at a time. If this number is reached, every new call discards
    an old one.
    """

    def __init__(self, hass, retry_limit=0, retry_delay=20, queue_limit=100):
        """Initialize the decorator."""
        self.hass = hass
        self.retry_limit = retry_limit
        self.retry_delay = timedelta(seconds=retry_delay)
        self.queue_limit = queue_limit

    def __call__(self, method):
        """Decorate the target method."""
        from homeassistant.helpers.event import track_point_in_utc_time

        @wraps(method)
        def wrapper(*args, **kwargs):
            """Wrapped method."""
            # pylint: disable=protected-access
            if not hasattr(wrapper, "_retry_queue"):
                wrapper._retry_queue = []

            def scheduled(retry=0, untrack=None, event=None):
                """Call the target method.

                It is called directly at the first time and then called
                scheduled within the Hass mainloop.
                """
                if untrack is not None:
                    wrapper._retry_queue.remove(untrack)

                # pylint: disable=broad-except
                try:
                    method(*args, **kwargs)
                except Exception as ex:
                    if retry == self.retry_limit:
                        raise
                    if len(wrapper._retry_queue) >= self.queue_limit:
                        last = wrapper._retry_queue.pop(0)
                        if 'remove' in last:
                            func = last['remove']
                            func()
                        if 'exc' in last:
                            _LOGGER.error(
                                "Retry queue overflow, drop oldest entry: %s",
                                str(last['exc']))

                    target = utcnow() + self.retry_delay
                    tracking = {'target': target}
                    remove = track_point_in_utc_time(self.hass,
                                                     partial(scheduled,
                                                             retry + 1,
                                                             tracking),
                                                     target)
                    tracking['remove'] = remove
                    tracking["exc"] = ex
                    wrapper._retry_queue.append(tracking)

            scheduled()
        return wrapper

"""
A component which allows you to send data to an Influx database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/influxdb/
"""
import logging

import re

import voluptuous as vol

from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN, CONF_HOST,
    CONF_PORT, CONF_SSL, CONF_VERIFY_SSL, CONF_USERNAME, CONF_PASSWORD,
    CONF_EXCLUDE, CONF_INCLUDE, CONF_DOMAINS, CONF_ENTITIES)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['influxdb==3.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_DB_NAME = 'database'
CONF_TAGS = 'tags'
CONF_DEFAULT_MEASUREMENT = 'default_measurement'
CONF_OVERRIDE_MEASUREMENT = 'override_measurement'
CONF_BLACKLIST_DOMAINS = "blacklist_domains"

DEFAULT_DATABASE = 'home_assistant'
DEFAULT_VERIFY_SSL = True
DOMAIN = 'influxdb'
TIMEOUT = 5

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
        vol.Optional(CONF_DEFAULT_MEASUREMENT): cv.string,
        vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string,
        vol.Optional(CONF_TAGS, default={}):
            vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


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
    default_measurement = conf.get(CONF_DEFAULT_MEASUREMENT)
    override_measurement = conf.get(CONF_OVERRIDE_MEASUREMENT)

    try:
        influx = InfluxDBClient(**kwargs)
        influx.query("SHOW SERIES LIMIT 1;", database=conf[CONF_DB_NAME])
    except exceptions.InfluxDBClientError as exc:
        _LOGGER.error("Database host is not accessible due to '%s', please "
                      "check your entries in the configuration file and that "
                      "the database exists and is READ/WRITE.", exc)
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

            _state = float(state_helper.state_as_number(state))
            _state_key = "value"
        except ValueError:
            _state = state.state
            _state_key = "state"

        if override_measurement:
            measurement = override_measurement
        else:
            measurement = state.attributes.get('unit_of_measurement')
            if measurement in (None, ''):
                if default_measurement:
                    measurement = default_measurement
                else:
                    measurement = state.entity_id

        json_body = [
            {
                'measurement': measurement,
                'tags': {
                    'domain': state.domain,
                    'entity_id': state.object_id,
                },
                'time': event.time_fired,
                'fields': {
                    _state_key: _state,
                }
            }
        ]

        non_digit_tail = re.compile(r'[\d.]+')
        non_decimal = re.compile(r'[^\d.]+')
        for key, value in state.attributes.items():
            if key != 'unit_of_measurement':
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
                    json_body[0]['fields'][new_key] = str(value)
                    if non_digit_tail.match(json_body[0]['fields'][new_key]):
                        json_body[0]['fields'][key] = float(
                            non_decimal.sub('', value))

        json_body[0]['tags'].update(tags)

        try:
            influx.write_points(json_body)
        except exceptions.InfluxDBClientError:
            _LOGGER.exception("Error saving event %s to InfluxDB", json_body)

    hass.bus.listen(EVENT_STATE_CHANGED, influx_event_listener)

    return True

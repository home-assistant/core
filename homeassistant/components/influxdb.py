"""
A component which allows you to send data to an Influx database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/influxdb/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN, CONF_HOST,
    CONF_PORT, CONF_SSL, CONF_VERIFY_SSL, CONF_USERNAME, CONF_BLACKLIST,
    CONF_PASSWORD, CONF_WHITELIST)
from homeassistant.helpers import state as state_helper
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['influxdb==3.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_DB_NAME = 'database'
CONF_TAGS = 'tags'

DEFAULT_DATABASE = 'home_assistant'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8086
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = False
DOMAIN = 'influxdb'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_BLACKLIST, default=[]):
            vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(CONF_DB_NAME, default=DEFAULT_DATABASE): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PORT, default=False): cv.boolean,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_TAGS, default={}):
            vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_WHITELIST, default=[]):
            vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=too-many-locals
def setup(hass, config):
    """Setup the InfluxDB component."""
    from influxdb import InfluxDBClient, exceptions

    conf = config[DOMAIN]

    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    database = conf.get(CONF_DB_NAME)
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    ssl = conf.get(CONF_SSL)
    verify_ssl = conf.get(CONF_VERIFY_SSL)
    blacklist = conf.get(CONF_BLACKLIST)
    whitelist = conf.get(CONF_WHITELIST)
    tags = conf.get(CONF_TAGS)

    try:
        influx = InfluxDBClient(
            host=host, port=port, username=username, password=password,
            database=database, ssl=ssl, verify_ssl=verify_ssl)
        influx.query("select * from /.*/ LIMIT 1;")
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
                state.entity_id in blacklist:
            return

        try:
            if len(whitelist) > 0 and state.entity_id not in whitelist:
                return

            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        measurement = state.attributes.get('unit_of_measurement')
        if measurement in (None, ''):
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
                    'value': _state,
                }
            }
        ]

        for key, value in state.attributes.items():
            if key != 'unit_of_measurement':
                json_body[0]['fields'][key] = value

        json_body[0]['tags'].update(tags)

        try:
            influx.write_points(json_body)
        except exceptions.InfluxDBClientError:
            _LOGGER.exception('Error saving event "%s" to InfluxDB', json_body)

    hass.bus.listen(EVENT_STATE_CHANGED, influx_event_listener)

    return True

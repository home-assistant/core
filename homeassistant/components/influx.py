"""
homeassistant.components.influx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
InfluxDB component which allows you to send data to an Influx database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/influx/

Configuration:

influx:
  host: localhost
  port: 8086
  dbname: home_assistant
  dbuser: DB_USER
  dbuser_password: DB_USER_PASSWORD
"""
import logging

import homeassistant.util as util
from homeassistant.helpers import validate_config
from homeassistant.const import (EVENT_STATE_CHANGED, STATE_ON, STATE_OFF,
                                 STATE_UNLOCKED, STATE_LOCKED, STATE_UNKNOWN)
from homeassistant.components.sun import (STATE_ABOVE_HORIZON,
                                          STATE_BELOW_HORIZON)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "influx"
DEPENDENCIES = ['recorder']

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8086
DEFAULT_DATABASE = 'home_assistant'

REQUIREMENTS = ['influxdb==2.10.0']

CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_DB_NAME = 'database'
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'


def setup(hass, config):
    """ Setup the Influx component. """

    from influxdb import InfluxDBClient, exceptions

    if not validate_config(config, {DOMAIN: ['host']}, _LOGGER):
        return False

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    dbname = util.convert(conf.get(CONF_DB_NAME), str, DEFAULT_DATABASE)
    username = util.convert(conf.get(CONF_USERNAME), str)
    password = util.convert(conf.get(CONF_PASSWORD), str)

    try:
        influx = InfluxDBClient(host=host, port=port, username=username,
                                password=password, database=dbname)
        databases = [i['name'] for i in influx.get_list_database()]
    except exceptions.InfluxDBClientError:
        _LOGGER.error("Database host is not accessible. "
                      "Please check your entries in the configuration file.")
        return False

    if dbname not in databases:
        _LOGGER.error("Database %s doesn't exist", dbname)
        return False

    def event_listener(event):
        """ Listen for new messages on the bus and sends them to Influx. """
        event_data = event.as_dict()

        if event_data['event_type'] is not EVENT_STATE_CHANGED:
            return

        state = event_data['data']['new_state']

        if state.state == STATE_ON or state.state == STATE_LOCKED or \
                state.state == STATE_ABOVE_HORIZON:
            _state = 1
        elif state.state == STATE_OFF or state.state == STATE_UNLOCKED or \
                state.state == STATE_UNKNOWN or \
                state.state == STATE_BELOW_HORIZON:
            _state = 0
        else:
            _state = state.state

        try:
            measurement = state.attributes['unit_of_measurement']
        except KeyError:
            measurement = '{}'.format(state.domain)

        json_body = [
            {
                'measurement': measurement,
                'tags': {
                    'domain': state.domain,
                    'entity_id': state.object_id,
                },
                'time': event_data['time_fired'],
                'fields': {
                    'value': _state,
                }
            }
        ]

        if json_body:
            try:
                influx.write_points(json_body)
            except exceptions.InfluxDBClientError:
                _LOGGER.error("Field type conflict")

    hass.bus.listen(EVENT_STATE_CHANGED, event_listener)

    return True

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
import requests
import socket

import homeassistant.util as util
from homeassistant.helpers import validate_config
from homeassistant.const import (MATCH_ALL)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "influx"
DEPENDENCIES = ['recorder']

INFLUX_CLIENT = None

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

    from influxdb import exceptions

    if not validate_config(config, {DOMAIN: ['host']}, _LOGGER):
        return False

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    dbname = util.convert(conf.get(CONF_DB_NAME), str, DEFAULT_DATABASE)
    username = util.convert(conf.get(CONF_USERNAME), str)
    password = util.convert(conf.get(CONF_PASSWORD), str)

    global INFLUX_CLIENT

    try:
        INFLUX_CLIENT = Influx(host, port, username, password, dbname)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        _LOGGER.error("Database is not accessible. "
                      "Please check your entries in the configuration file.")
        return False

    try:
        INFLUX_CLIENT.create_database(dbname)
    except exceptions.InfluxDBClientError:
        _LOGGER.info("Database '%s' already exists", dbname)

    INFLUX_CLIENT.switch_user(username, password)
    INFLUX_CLIENT.switch_database(dbname)

    def event_listener(event):
        """ Listen for new messages on the bus and sends them to Influx. """
        event_data = event.as_dict()
        json_body = []

        if event_data['event_type'] is not 'time_changed':
            try:
                entity_id = event_data['data']['entity_id']
                new_state = event_data['data']['new_state']

                json_body = [
                    {
                        "measurement": entity_id.split('.')[1],
                        "tags": {
                            "type":  entity_id.split('.')[0],
                        },
                        "time": event_data['time_fired'],
                        "fields": {
                            "value": new_state.state
                        }
                    }
                ]
            except KeyError:
                pass

        if json_body:
            INFLUX_CLIENT.write_data(json_body)

    hass.bus.listen(MATCH_ALL, event_listener)

    return True


# pylint: disable=too-many-arguments
class Influx(object):
    """ Implements the handling of an connection to an Influx database.. """

    def __init__(self, host, port, username, password, dbname):

        from influxdb import InfluxDBClient

        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._dbname = dbname

        self.client = InfluxDBClient(self._host, self._port, self._username,
                                     self._password, self._dbname)

    def switch_user(self, username, password):
        """ Switch the user to the given one. """
        self.client.switch_user(username, password)

    def create_database(self, dbname):
        """ Creates a new Influx database. """
        self.client.create_database(dbname)

    def switch_database(self, dbname):
        """ Switch the user to the given one. """
        return self.client.switch_database(dbname)

    def write_data(self, data):
        """ Writes data to Influx database. """
        self.client.write_points(data)

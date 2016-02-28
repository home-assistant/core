"""
homeassistant.components.sensor.teamspeak
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Monitors a teamspeak server

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.teamspeak/
"""
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.util import convert

REQUIREMENTS = ['ts3==0.7.1']
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Teamspeak Server'
ICON = 'mdi:microphone'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Teamspeak sensor. """
    name = config.get('name', DEFAULT_NAME)
    host = config.get('host')
    username = config.get('username')
    password = config.get('password')
    virtualserver_id = convert(config.get('virtualserver_id'), int, 0)

    if host is None:
        _LOGGER.error('No teamspeak host specified')
        return
    elif username is None:
        _LOGGER.error('No teamspeak username specified')
        return
    elif password is None:
        _LOGGER.error('No teamspeak password specified')
        return

    add_devices([
        TeamspeakSensor(name, host, username, password, virtualserver_id)
    ])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class TeamspeakSensor(Entity):
    """ A Teamspeak Server sensor. """

    def __init__(self, name, host, username, password, virtual_server_id):
        self._name = name
        self._state = None
        self._unit_of_measurement = 'Users'
        self._ts3conn = None

        self._host = host
        self._username = username
        self._password = password
        self._virtual_server_id = virtual_server_id

        self.connect()
        self.update()

    @property
    def name(self):
        """ The name of the sensor. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def icon(self):
        """ Icon to use in the frontend, if any. """
        return ICON

    def connect(self):
        """ Attempts to connect to TS3 server. """
        import ts3
        self._ts3conn = ts3.query.TS3Connection(self._host)
        try:
            self._ts3conn.login(
                client_login_name=self._username,
                client_login_password=self._password
            )
            self._ts3conn.use(sid=1)
            return True
        except ts3.query.TS3QueryError as err:
            _LOGGER.error("Teamspeak Login failed:" + err.resp.error["msg"])
            return False

    def update(self):
        """ Gets the latest data and updates the state. """
        if not self._ts3conn.is_connected():
            if not self.connect():
                return

        clients_online = int(
            self._ts3conn.serverlist()
            [self._virtual_server_id]['virtualserver_clientsonline']
        )
        query_clients_online = int(
            self._ts3conn.serverlist()
            [self._virtual_server_id]['virtualserver_queryclientsonline']
        )
        users_online = clients_online - query_clients_online
        self._state = users_online

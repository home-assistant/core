"""
homeassistant.components.sensor.teamspeak
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Monitors a teamspeak server

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.teamspeak/
"""
import logging
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['ts3==0.7.1']
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Teamspeak Server'
ATTR_SERVER_NAME = 'Name'
ATTR_MAX_USERS = 'Max. Users'
ATTR_UPTIME = 'Uptime (s)'
ATTR_STATUS = 'Status'
ICON = 'mdi:microphone'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Teamspeak sensor. """
    name = config.get('name', DEFAULT_NAME)
    host = config.get('host', None)
    username = config.get('username', None)
    password = config.get('password', None)
    virtualserver_id = config.get('virtualserver_id', 0)

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


class TeamspeakSensor(Entity):
    """ A Teamspeak Server sensor. """

    def __init__(self, name, host, username, password, virtual_server_id):
        import ts3
        self._name = name
        self._state = None
        self._unit_of_measurement = 'Users'
        self.info = None

        self._host = host
        self._username = username
        self._password = password
        self._virtual_server_id = virtual_server_id

        self._ts3conn = ts3.query.TS3Connection(self._host)

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
    def device_state_attributes(self):
        """ Returns the state attributes. """
        if self.info is not None:
            return {
                ATTR_SERVER_NAME: self.info['virtualserver_name'],
                ATTR_MAX_USERS: self.info['virtualserver_maxclients'],
                ATTR_UPTIME: self.info['virtualserver_uptime'],
                ATTR_STATUS: self.info['virtualserver_status']
            }

    @property
    def icon(self):
        """ Icon to use in the frontend, if any. """
        return ICON

    def connect(self):
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

        clientsOnline = int(
            self._ts3conn.serverlist()
            [self._virtual_server_id]['virtualserver_clientsonline']
        )
        queryClientsOnline = int(
            self._ts3conn.serverlist()
            [self._virtual_server_id]['virtualserver_queryclientsonline']
        )
        usersOnline = clientsOnline - queryClientsOnline
        self._state = usersOnline
        self.info = self._ts3conn.serverlist()[self._virtual_server_id]

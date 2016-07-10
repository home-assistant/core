"""
Support for Google travel time sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.google_travel_time/
"""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Return cached results if last update was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

ICON = 'mdi:email-outline'

CONF_USER = "user"
CONF_PASSWORD = "password"
CONF_SERVER = "server"
CONF_PORT = "port"
CONF_NAME = "name"
CONF_PERIOD = "frequency"

PLATFORM_SCHEMA = vol.Schema({
    vol.Required('platform'): 'imap',
    vol.Optional(CONF_NAME): vol.Coerce(str),
    vol.Required(CONF_USER): vol.Coerce(str),
    vol.Required(CONF_PASSWORD): vol.Coerce(str),
    vol.Required(CONF_SERVER): vol.Coerce(str),
    vol.Optional(CONF_PORT): vol.Coerce(int),
    vol.Optional(CONF_PERIOD): vol.Coerce(int),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the IMAP platform."""

    sensor = ImapSensor(config.get(CONF_NAME, None),
                        config.get(CONF_USER),
                        config.get(CONF_PASSWORD),
                        config.get(CONF_SERVER),
                        config.get(CONF_PORT, 993))

    if sensor.connection:
        add_devices([sensor])
    else:
        return False


class ImapSensor(Entity):
    """IMAP sensor class."""
    # pylint: disable=too-many-arguments
    def __init__(self, name, user, password, server, port):
        """Initialize the sensor."""
        self._name = name or user
        self._user = user
        self._password = password
        self._server = server
        self._port = port
        self._unread_count = 0
        self.connection = self._login()
        self.update()

    def _login(self):
        """Login to gmail and return a imap connection."""
        import imaplib
        try:
            connection = imaplib.IMAP4_SSL(self._server, self._port)
            connection.login(self._user, self._password)
            return connection
        except imaplib.IMAP4.error:
            _LOGGER.error("Failed to login to %s.", self._server)
            return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the number of unread emails."""
        return self._unread_count

    def update(self):
        """Check the number of unread emails."""
        import imaplib
        try:
            self.connection.select()
            self._unread_count = len(self.connection.search(
                None, 'UnSeen')[1][0].split())
        except imaplib.IMAP4.abort:
            _LOGGER.info("Connection to %s lost, attempting to reconnect",
                         self._server)
            try:
                self._login()
                self.update()
            except imaplib.IMAP4.error:
                _LOGGER.error("Failed to reconnect.")

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

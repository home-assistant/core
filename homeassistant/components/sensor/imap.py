"""
IMAP sensor support.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.imap/
"""
import logging
import voluptuous as vol

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:email-outline'

CONF_USER = "user"
CONF_PASSWORD = "password"
CONF_SERVER = "server"
CONF_PORT = "port"
CONF_NAME = "name"

DEFAULT_PORT = 993

PLATFORM_SCHEMA = vol.Schema({
    vol.Required('platform'): 'imap',
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_USER): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_SERVER): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the IMAP platform."""
    sensor = ImapSensor(config.get(CONF_NAME, None),
                        config.get(CONF_USER),
                        config.get(CONF_PASSWORD),
                        config.get(CONF_SERVER),
                        config.get(CONF_PORT, DEFAULT_PORT))

    if sensor.connection:
        add_devices([sensor])
    else:
        return False


class ImapSensor(Entity):
    """Representation of an IMAP sensor."""

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
        """Login and return an IMAP connection."""
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

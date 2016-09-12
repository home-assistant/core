"""
EMail sensor support.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.email/
"""
import logging
import datetime
import email
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_PORT, CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

CONF_SERVER = "server"
CONF_SENDERS = "senders"
CONF_VALUE_TEMPLATE = "value_template"

DEFAULT_PORT = 993

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_SERVER): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the EMail platform."""
    reader = EmailReader(
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_SERVER),
        config.get(CONF_PORT))

    sensor = EmailSensor(
        hass,
        reader,
        config.get(CONF_NAME, None) or config.get(CONF_USERNAME),
        config.get(CONF_SENDERS),
        config.get(CONF_VALUE_TEMPLATE))

    if sensor.connected:
        add_devices([sensor])
    else:
        return False


class EmailReader:
    """A class to read emails from an IMAP server."""

    def __init__(self, user, password, server, port):
        """Initialize the Email Reader."""
        self._user = user
        self._password = password
        self._server = server
        self._port = port
        self._last_id = None
        self.connection = None

    def connect(self):
        """Login and setup the connection."""
        import imaplib
        try:
            self.connection = imaplib.IMAP4_SSL(self._server, self._port)
            self.connection.login(self._user, self._password)
            return True
        except imaplib.IMAP4.error:
            _LOGGER.error("Failed to login to %s.", self._server)
            return False

    def _fetch_message(self, message_uid):
        """Get an email message from a message id."""
        _, message_data = self.connection.uid(
            'fetch',
            message_uid,
            '(RFC822)')

        raw_email = message_data[0][1]
        email_message = email.message_from_bytes(raw_email)
        return email_message

    def read_next(self):
        """Read the next email from the email server."""
        import imaplib
        try:

            self.connection.select()

            search = "SINCE {0:%d-%b-%y}".format(datetime.date.today())
            if self._last_id is not None:
                search = "UID {}:*".format(self._last_id)

            _, data = self.connection.search(None, search)
            messages = data[0].split()
            for message_uid in messages:
                if self._last_id is None or int(message_uid) > self._last_id:
                    self._last_id = int(message_uid)
                    return self._fetch_message(message_uid)

        except imaplib.IMAP4.error:
            _LOGGER.info(
                "Connection to %s lost, attempting to reconnect",
                self._server)
        try:
            self.connection = self.connect()
        except imaplib.IMAP4.error:
            _LOGGER.error("Failed to reconnect.")


class EmailSensor(Entity):
    """Representation of an EMail sensor."""

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-instance-attributes
    def __init__(self,
                 hass,
                 email_reader,
                 name,
                 allowed_senders,
                 value_template):
        """Initialize the sensor."""
        self.hass = hass
        self._email_reader = email_reader
        self._name = name
        self._allowed_senders = allowed_senders
        self._value_template = value_template
        self._last_id = None
        self._message = None
        self._state_attributes = None
        self.connected = self._email_reader.connect()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the number of unread emails."""
        return self._message

    @property
    def state_attributes(self):
        """Return other state attributes for the message."""
        return self._state_attributes

    def render_template(self, email_message):
        """Render the message template."""
        variables = {
            'from': str(email_message['From']),
            'subject': str(email_message['Subject']),
            'date': email_message['Date'],
            'body': email_message.get_payload()
        }
        return template.render(self.hass, self._value_template, variables)

    def sender_allowed(self, email_message):
        """Check if the sender is in the allowed senders list."""
        return str(email_message['From']).upper() in (
            sender.upper() for sender in self._allowed_senders)

    def update(self):
        """Read emails and publish state change."""
        while True:
            email_message = self._email_reader.read_next()
            if email_message is None:
                break

            if self.sender_allowed(email_message):
                message_body = email_message.get_payload()

                if self._value_template is not None:
                    message_body = self.render_template(email_message)

                self._message = message_body
                self._state_attributes = {
                    'from': str(email_message['From']),
                    'subject': str(email_message['Subject']),
                    'date': email_message['Date']
                }
                self.update_ha_state()
                self.update_ha_state()

"""Email sensor support."""
from collections import deque
import datetime
import email
import imaplib
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_DATE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONTENT_TYPE_TEXT_PLAIN,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SERVER = "server"
CONF_SENDERS = "senders"
CONF_FOLDER = "folder"

ATTR_FROM = "from"
ATTR_BODY = "body"
ATTR_SUBJECT = "subject"

DEFAULT_PORT = 993

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SERVER): cv.string,
        vol.Required(CONF_SENDERS): [cv.string],
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_FOLDER, default="INBOX"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Email sensor platform."""
    reader = EmailReader(
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_SERVER),
        config.get(CONF_PORT),
        config.get(CONF_FOLDER),
    )

    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass
    sensor = EmailContentSensor(
        hass,
        reader,
        config.get(CONF_NAME) or config.get(CONF_USERNAME),
        config.get(CONF_SENDERS),
        value_template,
    )

    if sensor.connected:
        add_entities([sensor], True)
    else:
        return False


class EmailReader:
    """A class to read emails from an IMAP server."""

    def __init__(self, user, password, server, port, folder):
        """Initialize the Email Reader."""
        self._user = user
        self._password = password
        self._server = server
        self._port = port
        self._folder = folder
        self._last_id = None
        self._unread_ids = deque([])
        self.connection = None

    def connect(self):
        """Login and setup the connection."""
        try:
            self.connection = imaplib.IMAP4_SSL(self._server, self._port)
            self.connection.login(self._user, self._password)
            return True
        except imaplib.IMAP4.error:
            _LOGGER.error("Failed to login to %s", self._server)
            return False

    def _fetch_message(self, message_uid):
        """Get an email message from a message id."""
        _, message_data = self.connection.uid("fetch", message_uid, "(RFC822)")

        if message_data is None:
            return None
        if message_data[0] is None:
            return None
        raw_email = message_data[0][1]
        email_message = email.message_from_bytes(raw_email)
        return email_message

    def read_next(self):
        """Read the next email from the email server."""
        try:
            self.connection.select(self._folder, readonly=True)

            if not self._unread_ids:
                search = f"SINCE {datetime.date.today():%d-%b-%Y}"
                if self._last_id is not None:
                    search = f"UID {self._last_id}:*"

                _, data = self.connection.uid("search", None, search)
                self._unread_ids = deque(data[0].split())

            while self._unread_ids:
                message_uid = self._unread_ids.popleft()
                if self._last_id is None or int(message_uid) > self._last_id:
                    self._last_id = int(message_uid)
                    return self._fetch_message(message_uid)

            return self._fetch_message(str(self._last_id))

        except imaplib.IMAP4.error:
            _LOGGER.info("Connection to %s lost, attempting to reconnect", self._server)
            try:
                self.connect()
                _LOGGER.info(
                    "Reconnect to %s succeeded, trying last message", self._server
                )
                if self._last_id is not None:
                    return self._fetch_message(str(self._last_id))
            except imaplib.IMAP4.error:
                _LOGGER.error("Failed to reconnect")

        return None


class EmailContentSensor(SensorEntity):
    """Representation of an EMail sensor."""

    def __init__(self, hass, email_reader, name, allowed_senders, value_template):
        """Initialize the sensor."""
        self.hass = hass
        self._email_reader = email_reader
        self._name = name
        self._allowed_senders = [sender.upper() for sender in allowed_senders]
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
    def native_value(self):
        """Return the current email state."""
        return self._message

    @property
    def extra_state_attributes(self):
        """Return other state attributes for the message."""
        return self._state_attributes

    def render_template(self, email_message):
        """Render the message template."""
        variables = {
            ATTR_FROM: EmailContentSensor.get_msg_sender(email_message),
            ATTR_SUBJECT: EmailContentSensor.get_msg_subject(email_message),
            ATTR_DATE: email_message["Date"],
            ATTR_BODY: EmailContentSensor.get_msg_text(email_message),
        }
        return self._value_template.render(variables, parse_result=False)

    def sender_allowed(self, email_message):
        """Check if the sender is in the allowed senders list."""
        return EmailContentSensor.get_msg_sender(email_message).upper() in (
            sender for sender in self._allowed_senders
        )

    @staticmethod
    def get_msg_sender(email_message):
        """Get the parsed message sender from the email."""
        return str(email.utils.parseaddr(email_message["From"])[1])

    @staticmethod
    def get_msg_subject(email_message):
        """Decode the message subject."""
        decoded_header = email.header.decode_header(email_message["Subject"])
        header = email.header.make_header(decoded_header)
        return str(header)

    @staticmethod
    def get_msg_text(email_message):
        """
        Get the message text from the email.

        Will look for text/plain or use text/html if not found.
        """
        message_text = None
        message_html = None
        message_untyped_text = None

        for part in email_message.walk():
            if part.get_content_type() == CONTENT_TYPE_TEXT_PLAIN:
                if message_text is None:
                    message_text = part.get_payload()
            elif part.get_content_type() == "text/html":
                if message_html is None:
                    message_html = part.get_payload()
            elif (
                part.get_content_type().startswith("text")
                and message_untyped_text is None
            ):
                message_untyped_text = part.get_payload()

        if message_text is not None:
            return message_text

        if message_html is not None:
            return message_html

        if message_untyped_text is not None:
            return message_untyped_text

        return email_message.get_payload()

    def update(self):
        """Read emails and publish state change."""
        email_message = self._email_reader.read_next()

        if email_message is None:
            self._message = None
            self._state_attributes = {}
            return

        if self.sender_allowed(email_message):
            message = EmailContentSensor.get_msg_subject(email_message)

            if self._value_template is not None:
                message = self.render_template(email_message)

            self._message = message
            self._state_attributes = {
                ATTR_FROM: EmailContentSensor.get_msg_sender(email_message),
                ATTR_SUBJECT: EmailContentSensor.get_msg_subject(email_message),
                ATTR_DATE: email_message["Date"],
                ATTR_BODY: EmailContentSensor.get_msg_text(email_message),
            }

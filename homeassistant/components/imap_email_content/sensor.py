"""Email sensor support."""
from __future__ import annotations

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
    CONF_VERIFY_SSL,
    CONTENT_TYPE_TEXT_PLAIN,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.ssl import client_context

from .const import (
    ATTR_BODY,
    ATTR_FROM,
    ATTR_SUBJECT,
    CONF_FOLDER,
    CONF_SENDERS,
    CONF_SERVER,
    DEFAULT_PORT,
)
from .repairs import async_process_issue

_LOGGER = logging.getLogger(__name__)

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
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Email sensor platform."""
    reader = EmailReader(
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[CONF_SERVER],
        config[CONF_PORT],
        config[CONF_FOLDER],
        config[CONF_VERIFY_SSL],
    )

    if (value_template := config.get(CONF_VALUE_TEMPLATE)) is not None:
        value_template.hass = hass
    sensor = EmailContentSensor(
        hass,
        reader,
        config.get(CONF_NAME) or config[CONF_USERNAME],
        config[CONF_SENDERS],
        value_template,
    )

    hass.add_job(async_process_issue, hass, config)

    if sensor.connected:
        add_entities([sensor], True)


class EmailReader:
    """A class to read emails from an IMAP server."""

    def __init__(self, user, password, server, port, folder, verify_ssl):
        """Initialize the Email Reader."""
        self._user = user
        self._password = password
        self._server = server
        self._port = port
        self._folder = folder
        self._verify_ssl = verify_ssl
        self._last_id = None
        self._last_message = None
        self._unread_ids = deque([])
        self.connection = None

    @property
    def last_id(self) -> int | None:
        """Return last email uid that was processed."""
        return self._last_id

    @property
    def last_unread_id(self) -> int | None:
        """Return last email uid received."""
        # We assume the last id in the list is the last unread id
        # We cannot know if that is the newest one, because it could arrive later
        # https://stackoverflow.com/questions/12409862/python-imap-the-order-of-uids
        if self._unread_ids:
            return int(self._unread_ids[-1])
        return self._last_id

    def connect(self):
        """Login and setup the connection."""
        ssl_context = client_context() if self._verify_ssl else None
        try:
            self.connection = imaplib.IMAP4_SSL(
                self._server, self._port, ssl_context=ssl_context
            )
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

            if self._last_id is None:
                # search for today and yesterday
                time_from = datetime.datetime.now() - datetime.timedelta(days=1)
                search = f"SINCE {time_from:%d-%b-%Y}"
            else:
                search = f"UID {self._last_id}:*"

            _, data = self.connection.uid("search", None, search)
            self._unread_ids = deque(data[0].split())
            while self._unread_ids:
                message_uid = self._unread_ids.popleft()
                if self._last_id is None or int(message_uid) > self._last_id:
                    self._last_id = int(message_uid)
                    self._last_message = self._fetch_message(message_uid)
                    return self._last_message

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
        """Get the message text from the email.

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

    def update(self) -> None:
        """Read emails and publish state change."""
        email_message = self._email_reader.read_next()
        while (
            self._last_id is None or self._last_id != self._email_reader.last_unread_id
        ):
            if email_message is None:
                self._message = None
                self._state_attributes = {}
                return

            self._last_id = self._email_reader.last_id

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

            if self._last_id == self._email_reader.last_unread_id:
                break
            email_message = self._email_reader.read_next()

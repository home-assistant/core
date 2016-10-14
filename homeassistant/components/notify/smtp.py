"""
Mail (SMTP) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.smtp/
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_DATA, PLATFORM_SCHEMA,
    BaseNotificationService)
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_PORT, CONF_SENDER, CONF_RECIPIENT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_IMAGES = 'images'  # optional embedded image file attachments

CONF_STARTTLS = 'starttls'
CONF_DEBUG = 'debug'
CONF_SERVER = 'server'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 25
DEFAULT_DEBUG = False
DEFAULT_STARTTLS = False

# pylint: disable=no-value-for-parameter
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RECIPIENT): vol.Email(),
    vol.Optional(CONF_SERVER, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SENDER): vol.Email(),
    vol.Optional(CONF_STARTTLS, default=DEFAULT_STARTTLS): cv.boolean,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): cv.boolean,
})


def get_service(hass, config):
    """Get the mail notification service."""
    mail_service = MailNotificationService(
        config.get(CONF_SERVER),
        config.get(CONF_PORT),
        config.get(CONF_SENDER),
        config.get(CONF_STARTTLS),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_RECIPIENT),
        config.get(CONF_DEBUG))

    if mail_service.connection_is_valid():
        return mail_service
    else:
        return None


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class MailNotificationService(BaseNotificationService):
    """Implement the notification service for E-Mail messages."""

    # pylint: disable=too-many-arguments
    def __init__(self, server, port, sender, starttls, username,
                 password, recipient, debug):
        """Initialize the service."""
        self._server = server
        self._port = port
        self._sender = sender
        self.starttls = starttls
        self.username = username
        self.password = password
        self.recipient = recipient
        self.debug = debug
        self.tries = 2

    def connect(self):
        """Connect/authenticate to SMTP Server."""
        mail = smtplib.SMTP(self._server, self._port, timeout=5)
        mail.set_debuglevel(self.debug)
        mail.ehlo_or_helo_if_needed()
        if self.starttls:
            mail.starttls()
            mail.ehlo()
        if self.username and self.password:
            mail.login(self.username, self.password)
        return mail

    def connection_is_valid(self):
        """Check for valid config, verify connectivity."""
        server = None
        try:
            server = self.connect()
        except smtplib.socket.gaierror:
            _LOGGER.exception(
                "SMTP server not found (%s:%s). "
                "Please check the IP address or hostname of your SMTP server",
                self._server, self._port)
            return False

        except (smtplib.SMTPAuthenticationError, ConnectionRefusedError):
            _LOGGER.exception(
                "Login not possible. "
                "Please check your setting and/or your credentials")
            return False

        finally:
            if server:
                server.quit()

        return True

    def send_message(self, message="", **kwargs):
        """
        Build and send a message to a user.

        Will send plain text normally, or will build a multipart HTML message
        with inline image attachments if images config is defined.
        """
        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA)

        if data:
            msg = _build_multipart_msg(message, images=data.get(ATTR_IMAGES))
        else:
            msg = _build_text_msg(message)

        msg['Subject'] = subject
        msg['To'] = self.recipient
        msg['From'] = self._sender
        msg['X-Mailer'] = 'HomeAssistant'

        return self._send_email(msg)

    def _send_email(self, msg):
        """Send the message."""
        mail = self.connect()
        for _ in range(self.tries):
            try:
                mail.sendmail(self._sender, self.recipient,
                              msg.as_string())
                break
            except smtplib.SMTPException:
                _LOGGER.warning('SMTPException sending mail: '
                                'retrying connection')
                mail.quit()
                mail = self.connect()

        mail.quit()


def _build_text_msg(message):
    """Build plaintext email."""
    _LOGGER.debug('Building plain text email')
    return MIMEText(message)


def _build_multipart_msg(message, images):
    """Build Multipart message with in-line images."""
    _LOGGER.debug('Building multipart email with embedded attachment(s)')
    msg = MIMEMultipart('related')
    msg_alt = MIMEMultipart('alternative')
    msg.attach(msg_alt)
    body_txt = MIMEText(message)
    msg_alt.attach(body_txt)
    body_text = ['<p>{}</p><br>'.format(message)]

    for atch_num, atch_name in enumerate(images):
        cid = 'image{}'.format(atch_num)
        body_text.append('<img src="cid:{}"><br>'.format(cid))
        try:
            with open(atch_name, 'rb') as attachment_file:
                attachment = MIMEImage(attachment_file.read())
                msg.attach(attachment)
                attachment.add_header('Content-ID', '<{}>'.format(cid))
        except FileNotFoundError:
            _LOGGER.warning('Attachment %s not found. Skipping',
                            atch_name)

    body_html = MIMEText(''.join(body_text), 'html')
    msg_alt.attach(body_html)
    return msg

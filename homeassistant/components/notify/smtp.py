"""
Mail (SMTP) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.smtp/
"""
import logging
import smtplib
from email.mime.text import MIMEText

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the mail notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['recipient']},
                           _LOGGER):
        return None

    smtp_server = config.get('server', 'localhost')
    port = int(config.get('port', '25'))
    username = config.get('username', None)
    password = config.get('password', None)
    starttls = int(config.get('starttls', 0))
    debug = config.get('debug', 0)

    server = None
    try:
        server = smtplib.SMTP(smtp_server, port, timeout=5)
        server.set_debuglevel(debug)
        server.ehlo()
        if starttls == 1:
            server.starttls()
            server.ehlo()
        if username and password:
            try:
                server.login(username, password)

            except (smtplib.SMTPException, smtplib.SMTPSenderRefused):
                _LOGGER.exception("Please check your settings.")
                return None

    except smtplib.socket.gaierror:
        _LOGGER.exception(
            "SMTP server not found (%s:%s). "
            "Please check the IP address or hostname of your SMTP server.",
            smtp_server, port)

        return None

    except smtplib.SMTPAuthenticationError:
        _LOGGER.exception(
            "Login not possible. "
            "Please check your setting and/or your credentials.")

        return None

    finally:
        if server:
            server.quit()

    return MailNotificationService(
        smtp_server, port, config['sender'], starttls, username, password,
        config['recipient'], debug)


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
        if self.starttls == 1:
            mail.starttls()
            mail.ehlo()
        if self.username and self.password:
            mail.login(self.username, self.password)
        return mail

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        mail = self.connect()
        subject = kwargs.get(ATTR_TITLE)

        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['To'] = self.recipient
        msg['From'] = self._sender
        msg['X-Mailer'] = 'HomeAssistant'

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

"""
homeassistant.components.notify.smtp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Mail (SMTP) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.smtp/
"""
import logging
import smtplib
from email.mime.text import MIMEText

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """ Get the mail notification service. """

    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['server', 'port', 'sender', 'username',
                                     'password', 'recipient']},
                           _LOGGER):
        return None

    smtp_server = config['server']
    port = int(config['port'])
    username = config['username']
    password = config['password']
    starttls = int(config['starttls'])

    server = None
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.ehlo()
        if starttls == 1:
            server.starttls()
            server.ehlo()

        try:
            server.login(username, password)

        except (smtplib.SMTPException, smtplib.SMTPSenderRefused):
            _LOGGER.exception("Please check your settings.")

            return None

    except smtplib.socket.gaierror:
        _LOGGER.exception(
            "SMTP server not found. "
            "Please check the IP address or hostname of your SMTP server.")

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
        config['recipient'])


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class MailNotificationService(BaseNotificationService):
    """ Implements notification service for E-Mail messages. """

    # pylint: disable=too-many-arguments
    def __init__(self, server, port, sender, starttls, username,
                 password, recipient):
        self._server = server
        self._port = port
        self._sender = sender
        self.starttls = starttls
        self.username = username
        self.password = password
        self.recipient = recipient
        self.tries = 2
        self.mail = None

        self.connect()

    def connect(self):
        """ Connect/Authenticate to SMTP Server """

        self.mail = smtplib.SMTP(self._server, self._port)
        self.mail.ehlo_or_helo_if_needed()
        if self.starttls == 1:
            self.mail.starttls()
            self.mail.ehlo()
        self.mail.login(self.username, self.password)

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        subject = kwargs.get(ATTR_TITLE)

        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['To'] = self.recipient
        msg['From'] = self._sender
        msg['X-Mailer'] = 'HomeAssistant'

        for _ in range(self.tries):
            try:
                self.mail.sendmail(self._sender, self.recipient,
                                   msg.as_string())
                break
            except smtplib.SMTPException:
                _LOGGER.warning('SMTPException sending mail: '
                                'retrying connection')
                self.connect()

"""
homeassistant.components.notify.mail
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Mail notification service.

Configuration:

To use the Mail notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: mail
  server: MAIL_SERVER
  port: YOUR_SMTP_PORT
  sender: SENDER_EMAIL_ADDRESS
  starttls: 1 or 0
  username: YOUR_SMTP_USERNAME
  password: YOUR_SMTP_PASSWORD
  recipient: YOUR_RECIPIENT

Variables:

server
*Required
SMTP server which is used to end the notifications. For Google Mail, eg.
smtp.gmail.com. Keep in mind that Google has some extra layers of protection
which need special attention (Hint: 'Less secure apps').

port
*Required
The port that the SMTP server is using, eg. 587 for Google Mail and STARTTLS
or 465/993 depending on your SMTP servers.

sender
*Required
E-Mail address of the sender.

starttls
*Optional
Enables STARTTLS, eg. 1 or 0.

username
*Required
Username for the SMTP account.

password
*Required
Password for the SMTP server that belongs to the given username. If the
password contains a colon it need to be wrapped in apostrophes.

recipient
*Required
Recipient of the notification.
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

    if not validate_config(config,
                           {DOMAIN: ['server',
                                     'port',
                                     'sender',
                                     'username',
                                     'password',
                                     'recipient']},
                           _LOGGER):
        return None

    smtp_server = config[DOMAIN]['server']
    port = int(config[DOMAIN]['port'])
    username = config[DOMAIN]['username']
    password = config[DOMAIN]['password']

    server = None
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.ehlo()
        if int(config[DOMAIN]['starttls']) == 1:
            server.starttls()
            server.ehlo()

        try:
            server.login(username, password)

        except (smtplib.SMTPException, smtplib.SMTPSenderRefused) as error:
            _LOGGER.exception(error,
                              "Please check your settings.")

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

    if server:
        server.quit()

    return MailNotificationService(
        config[DOMAIN]['server'],
        config[DOMAIN]['port'],
        config[DOMAIN]['sender'],
        config[DOMAIN]['starttls'],
        config[DOMAIN]['username'],
        config[DOMAIN]['password'],
        config[DOMAIN]['recipient']
        )


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class MailNotificationService(BaseNotificationService):
    """ Implements notification service for E-Mail messages. """

    # pylint: disable=too-many-arguments
    def __init__(self, server, port, sender, starttls, username,
                 password, recipient):
        self._server = server
        self._port = port
        self._sender = sender
        self.starttls = int(starttls)
        self.username = username
        self.password = password
        self.recipient = recipient

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

        self.mail.sendmail(self._sender, self.recipient, msg.as_string())

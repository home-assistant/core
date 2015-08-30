"""
homeassistant.components.notify.xmpp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Jabber (XMPP) notification service.

Configuration:

To use the Jabber notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: xmpp
  sender: YOUR_JID
  password: YOUR_JABBER_ACCOUNT_PASSWORD
  recipient: YOUR_RECIPIENT

Variables:

sender
*Required
The Jabber ID (JID) that will act as origin of the messages. Add your JID
including the domain, e.g. your_name@jabber.org.

password
*Required
The password for your given Jabber account.

recipient
*Required
The Jabber ID (JID) that will receive the messages.
"""
import logging

_LOGGER = logging.getLogger(__name__)

try:
    import sleekxmpp

except ImportError:
    _LOGGER.exception(
        "Unable to import sleekxmpp. "
        "Did you maybe not install the 'SleekXMPP' package?")

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)

REQUIREMENTS = ['sleekxmpp==1.3.1', 'dnspython3==1.12.0']


def get_service(hass, config):
    """ Get the Jabber (XMPP) notification service. """

    if not validate_config(config,
                           {DOMAIN: ['sender',
                                     'password',
                                     'recipient']},
                           _LOGGER):
        return None

    try:
        SendNotificationBot(config[DOMAIN]['sender'] + '/home-assistant',
                            config[DOMAIN]['password'],
                            config[DOMAIN]['recipient'],
                            '')
    except ImportError:
        _LOGGER.exception(
            "Unable to contact jabber server."
            "Please check your credentials.")

        return None

    return XmppNotificationService(config[DOMAIN]['sender'],
                                   config[DOMAIN]['password'],
                                   config[DOMAIN]['recipient'])


# pylint: disable=too-few-public-methods
class XmppNotificationService(BaseNotificationService):
    """ Implements notification service for Jabber (XMPP). """

    def __init__(self, sender, password, recipient):
        self._sender = sender
        self._password = password
        self._recipient = recipient

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)
        data = title + ": " + message

        SendNotificationBot(self._sender + '/home-assistant',
                            self._password,
                            self._recipient,
                            data)


class SendNotificationBot(sleekxmpp.ClientXMPP):
    """ Service for sending Jabber (XMPP) messages. """

    def __init__(self, jid, password, recipient, msg):

        super(SendNotificationBot, self).__init__(jid, password)

        logging.basicConfig(level=logging.ERROR)

        self.recipient = recipient
        self.msg = msg

        self.use_tls = True
        self.use_ipv6 = False
        self.add_event_handler('failed_auth', self.check_credentials)
        self.add_event_handler('session_start', self.start)
        self.connect()
        self.process(block=False)

    def start(self, event):
        """ Starts the communication and sends the message. """
        self.send_presence()
        self.get_roster()
        self.send_message(mto=self.recipient, mbody=self.msg, mtype='chat')
        self.disconnect(wait=True)

    def check_credentials(self, event):
        """" Disconnect from the server if credentials are invalid. """
        self.disconnect()

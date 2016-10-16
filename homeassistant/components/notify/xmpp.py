"""
Jabber (XMPP) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.xmpp/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_PASSWORD, CONF_SENDER, CONF_RECIPIENT

REQUIREMENTS = ['sleekxmpp==1.3.1',
                'dnspython3==1.14.0',
                'pyasn1==0.1.9',
                'pyasn1-modules==0.0.8']


CONF_TLS = 'tls'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENDER): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
    vol.Optional(CONF_TLS, default=True): cv.boolean,
})


_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the Jabber (XMPP) notification service."""
    return XmppNotificationService(
        config.get('sender'),
        config.get('password'),
        config.get('recipient'),
        config.get('tls'))


# pylint: disable=too-few-public-methods
class XmppNotificationService(BaseNotificationService):
    """Implement the notification service for Jabber (XMPP)."""

    def __init__(self, sender, password, recipient, tls):
        """Initialize the service."""
        self._sender = sender
        self._password = password
        self._recipient = recipient
        self._tls = tls

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = "{}: {}".format(title, message) if title else message

        send_message(self._sender + '/home-assistant', self._password,
                     self._recipient, self._tls, data)


def send_message(sender, password, recipient, use_tls, message):
    """Send a message over XMPP."""
    import sleekxmpp

    class SendNotificationBot(sleekxmpp.ClientXMPP):
        """Service for sending Jabber (XMPP) messages."""

        def __init__(self):
            """Initialize the Jabber Bot."""
            super(SendNotificationBot, self).__init__(sender, password)

            logging.basicConfig(level=logging.ERROR)

            self.use_tls = use_tls
            self.use_ipv6 = False
            self.add_event_handler('failed_auth', self.check_credentials)
            self.add_event_handler('session_start', self.start)
            self.connect(use_tls=self.use_tls, use_ssl=False)
            self.process()

        def start(self, event):
            """Start the communication and sends the message."""
            self.send_presence()
            self.get_roster()
            self.send_message(mto=recipient, mbody=message, mtype='chat')
            self.disconnect(wait=True)

        def check_credentials(self, event):
            """"Disconnect from the server if credentials are invalid."""
            self.disconnect()

    SendNotificationBot()

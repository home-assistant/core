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
from homeassistant.const import (
    CONF_PASSWORD, CONF_SENDER, CONF_RECIPIENT, CONF_ROOM)

REQUIREMENTS = ['sleekxmpp==1.3.2',
                'dnspython3==1.15.0',
                'pyasn1==0.3.7',
                'pyasn1-modules==0.1.5']

_LOGGER = logging.getLogger(__name__)

CONF_TLS = 'tls'
CONF_VERIFY = 'verify'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENDER): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
    vol.Optional(CONF_TLS, default=True): cv.boolean,
    vol.Optional(CONF_VERIFY, default=True): cv.boolean,
    vol.Optional(CONF_ROOM, default=''): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Jabber (XMPP) notification service."""
    return XmppNotificationService(
        config.get(CONF_SENDER), config.get(CONF_PASSWORD),
        config.get(CONF_RECIPIENT), config.get(CONF_TLS),
        config.get(CONF_VERIFY), config.get(CONF_ROOM))


class XmppNotificationService(BaseNotificationService):
    """Implement the notification service for Jabber (XMPP)."""

    def __init__(self, sender, password, recipient, tls, verify, room):
        """Initialize the service."""
        self._sender = sender
        self._password = password
        self._recipient = recipient
        self._tls = tls
        self._verify = verify
        self._room = room

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = '{}: {}'.format(title, message) if title else message

        send_message('{}/home-assistant'.format(self._sender),
                     self._password, self._recipient, self._tls,
                     self._verify, self._room, data)


def send_message(sender, password, recipient, use_tls,
                 verify_certificate, room, message):
    """Send a message over XMPP."""
    import sleekxmpp

    class SendNotificationBot(sleekxmpp.ClientXMPP):
        """Service for sending Jabber (XMPP) messages."""

        def __init__(self):
            """Initialize the Jabber Bot."""
            super(SendNotificationBot, self).__init__(sender, password)

            self.use_tls = use_tls
            self.use_ipv6 = False
            self.add_event_handler('failed_auth', self.check_credentials)
            self.add_event_handler('session_start', self.start)
            if room:
                self.register_plugin('xep_0045')  # MUC
            if not verify_certificate:
                self.add_event_handler('ssl_invalid_cert',
                                       self.discard_ssl_invalid_cert)

            self.connect(use_tls=self.use_tls, use_ssl=False)
            self.process()

        def start(self, event):
            """Start the communication and sends the message."""
            self.send_presence()
            self.get_roster()

            if room:
                _LOGGER.debug("Joining room %s.", room)
                self.plugin['xep_0045'].joinMUC(room, sender, wait=True)
                self.send_message(mto=room, mbody=message, mtype='groupchat')
            else:
                self.send_message(mto=recipient, mbody=message, mtype='chat')
            self.disconnect(wait=True)

        def check_credentials(self, event):
            """Disconnect from the server if credentials are invalid."""
            self.disconnect()

        @staticmethod
        def discard_ssl_invalid_cert(event):
            """Do nothing if ssl certificate is invalid."""
            _LOGGER.info('Ignoring invalid ssl certificate as requested.')
            return

    SendNotificationBot()

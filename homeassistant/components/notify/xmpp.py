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

REQUIREMENTS = ['slixmpp==1.4.0',
                'aiodns==1.1.1',
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


async def async_get_service(hass, config, discovery_info=None):
    """Get the Jabber (XMPP) notification service."""
    _LOGGER.debug("async_get_service")
    return XmppNotificationService(
        config.get(CONF_SENDER), config.get(CONF_PASSWORD),
        config.get(CONF_RECIPIENT), config.get(CONF_TLS),
        config.get(CONF_VERIFY), config.get(CONF_ROOM), hass.loop)


class XmppNotificationService(BaseNotificationService):
    """Implement the notification service for Jabber (XMPP)."""

    def __init__(self, sender, password, recipient, tls, verify, room, loop):
        """Initialize the service."""
        self._loop = loop
        self._sender = sender
        self._password = password
        self._recipient = recipient
        self._tls = tls
        self._verify = verify
        self._room = room
        _LOGGER.debug("XmppNotificationService __init__")

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        _LOGGER.debug("XmppNotificationService async_send_message 1")
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = '{}: {}'.format(title, message) if title else message

        # TODO allow /home-assistant part of the resource to be configured
        await async_send_message(
            '{}/home-assistant'.format(self._sender),
            self._password, self._recipient, self._tls,
            self._verify, self._room, self._loop, data)


async def async_send_message(sender, password, recipient, use_tls,
                             verify_certificate, room, loop, message):
    """Send a message over XMPP."""
    import slixmpp

    class SendNotificationBot(slixmpp.ClientXMPP):
        """Service for sending Jabber (XMPP) messages."""

        def __init__(self):
            """Initialize the Jabber Bot."""
            super(SendNotificationBot, self).__init__(sender, password)
            _LOGGER.debug("async_send_message SendNotificationBot __init__")

            # need hass.loop!!
            self.loop = loop

            self.force_starttls = use_tls
            self.use_ipv6 = False
            self.add_event_handler(
                'failed_auth', self.disconnect_on_login_fail)
            self.add_event_handler('session_start', self.start)
            # TODO test room
            if room:
                self.register_plugin('xep_0045')  # MUC
            if not verify_certificate:
                self.add_event_handler('ssl_invalid_cert',
                                       self.discard_ssl_invalid_cert)

            _LOGGER.debug("before connect")
            self.connect(force_starttls=self.force_starttls, use_ssl=False)

        def start(self, event):
            """Start the communication and sends the message."""
            _LOGGER.debug("event handler callback called on start")

            self.send_presence()
            self.get_roster()
            _LOGGER.debug("sender {}, message: {}".format(sender, message))
            if room:
                _LOGGER.debug("Joining room %s.", room)
                self.plugin['xep_0045'].join_muc(room, sender, wait=True)
                self.send_message(mto=room, mbody=message, mtype='groupchat')
            else:
                self.send_message(mto=recipient, mbody=message, mtype='chat')
            self.disconnect(wait=True)

        def disconnect_on_login_fail(self, event):
            """Disconnect from the server if credentials are invalid."""
            _LOGGER.debug("event handler callback called "
                          "on disconnect on login fail")
            self.disconnect()

        @staticmethod
        def discard_ssl_invalid_cert(event):
            """Do nothing if ssl certificate is invalid."""
            _LOGGER.debug("event handler callback called "
                          "on discard_ssl_invalid_cert")
            _LOGGER.info('Ignoring invalid ssl certificate as requested.')

    SendNotificationBot()

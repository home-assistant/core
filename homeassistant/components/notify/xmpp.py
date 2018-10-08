"""
Jabber (XMPP) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.xmpp/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_PASSWORD, CONF_SENDER, CONF_RECIPIENT, CONF_ROOM)


REQUIREMENTS = ['aioxmpp==0.10.1',
                'lxml==4.2.5',
                'sortedcollections==1.0.1',
                'tzlocal==1.5.1',
                'pyOpenSSL==18.0.0',
                'pyasn1==0.4.4',
                'pyasn1-modules==0.2.2',
                'aiosasl==0.3.1',
                'multidict==4.4.2',
                'aioopenssl==0.4.0',
                ##
                #'sleekxmpp==1.3.2',
                #'dnspython3==1.15.0',
                #'pyasn1==0.3.7',
                #'pyasn1-modules==0.1.5'
                ]

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

# not 'async def' but @callback because of:
# https://developers.home-assistant.io/docs/en/asyncio_categorizing_functions.html#why-even-have-callbacks
#@callback
# FIXXXXXME
async def async_get_service(hass, config, discovery_info=None):
    """Get the Jabber (XMPP) notification service."""
    return XmppNotificationService(
        config.get(CONF_SENDER), config.get(CONF_PASSWORD),
        config.get(CONF_RECIPIENT), config.get(CONF_TLS),
        config.get(CONF_VERIFY), config.get(CONF_ROOM), hass.loop)

class XmppNotificationService(BaseNotificationService):
    """Implement the notification service for Jabber (XMPP)."""

    def __init__(
            self, sender, password, recipient, tls, verify, room, loop):
        """Initialize the service."""
        self._loop = loop
        self._sender = sender
        self._password = password
        self._recipient = recipient
        self._tls = tls
        self._verify = verify
        self._room = room

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = '{}: {}'.format(title, message) if title else message
        _LOGGER.debug("before return async_send_message")

        return async_send_message('{}/home-assistant'.format(self._sender),
                     self._password, self._recipient, self._tls,
                     self._verify, self._room, self._loop, data)


async def async_send_message(sender, password, recipient, use_tls,
                 verify_certificate, room, loop, message):
    """Send a message over XMPP."""
    import aioxmpp

    class SendNotificationBot(aioxmpp.PresenceManagedClient):
        """Service for sending Jabber (XMPP) messages."""

        def __init__(self):
            """Initialize the Jabber Bot."""
            _LOGGER.debug("init of aioxmpp version {}".format(aioxmpp.__version__))
            super(SendNotificationBot, self).__init__(
                aioxmpp.JID.fromstr(sender),
                aioxmpp.make_security_layer(password),
                negotiation_timeout=timedelta(seconds=10),
                loop=loop,
            )
            # FIXXXXXME MUC for room
            self.start()

        async def start(self):
            """Start the communication and sends the message."""
            super(SendNotificationBot, self).start()
            async with self.connected() as stream:
                await asyncio.sleep(10)
                msg = aioxmpp.Message(
                    to=recipient,
                    type_=aioxmpp.MessageType.CHAT,
                      )
                # None is for "default language"
                msg.body[None] = message

                await self.send(msg)
            # FIXXXXXXXME join room
            self.stop()

    SendNotificationBot()

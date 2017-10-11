"""
IMAP sensor support.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.imap/
"""
import logging
import asyncio
import async_timeout

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['aioimaplib==0.7.12']

CONF_SERVER = 'server'

DEFAULT_PORT = 993

ICON = 'mdi:email-outline'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_SERVER): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the IMAP platform."""
    sensor = ImapSensor(config.get(CONF_NAME),
                        config.get(CONF_USERNAME),
                        config.get(CONF_PASSWORD),
                        config.get(CONF_SERVER),
                        config.get(CONF_PORT))

    if not (yield from sensor.connection()):
        raise PlatformNotReady

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.shutdown())
    async_add_devices([sensor], True)


class ImapSensor(Entity):
    """Representation of an IMAP sensor."""

    def __init__(self, name, user, password, server, port):
        """Initialize the sensor."""
        self._name = name or user
        self._user = user
        self._password = password
        self._server = server
        self._port = port
        self._unread_count = 0
        self._connection = None
        self._does_push = None
        self._idle_loop_task = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        if not self.should_poll:
            self._idle_loop_task = self.hass.loop.create_task(self.idle_loop())

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def state(self):
        """Return the number of unread emails."""
        return self._unread_count

    @property
    def available(self):
        """Return the availability of the device."""
        return self._connection is not None

    @property
    def should_poll(self):
        """Return if polling is needed."""
        return not self._does_push

    @asyncio.coroutine
    def connection(self):
        """Return a connection to the server, establishing it if necessary."""
        import aioimaplib

        if self._connection is None:
            try:
                self._connection = aioimaplib.IMAP4_SSL(
                    self._server, self._port)
                yield from self._connection.wait_hello_from_server()
                yield from self._connection.login(self._user, self._password)
                yield from self._connection.select()
                self._does_push = self._connection.has_capability('IDLE')
            except (aioimaplib.AioImapException, asyncio.TimeoutError):
                self._connection = None

        return self._connection

    @asyncio.coroutine
    def idle_loop(self):
        """Wait for data pushed from server."""
        import aioimaplib

        while True:
            try:
                if (yield from self.connection()):
                    yield from self.refresh_unread_count()
                    yield from self.async_update_ha_state()

                    idle = yield from self._connection.idle_start()
                    yield from self._connection.wait_server_push()
                    self._connection.idle_done()
                    with async_timeout.timeout(10):
                        yield from idle
                else:
                    yield from self.async_update_ha_state()
            except (aioimaplib.AioImapException, asyncio.TimeoutError):
                self.disconnected()

    @asyncio.coroutine
    def async_update(self):
        """Periodic polling of state."""
        import aioimaplib

        try:
            if (yield from self.connection()):
                yield from self.refresh_unread_count()
        except (aioimaplib.AioImapException, asyncio.TimeoutError):
            self.disconnected()

    @asyncio.coroutine
    def refresh_unread_count(self):
        """Check the number of unread emails."""
        if self._connection:
            yield from self._connection.noop()
            _, lines = yield from self._connection.search('UnSeen UnDeleted')
            self._unread_count = len(lines[0].split())

    def disconnected(self):
        """Forget the connection after it was lost."""
        _LOGGER.warning("Lost %s (will attempt to reconnect)", self._server)
        self._connection = None

    @asyncio.coroutine
    def shutdown(self):
        """Close resources."""
        if self._connection:
            if self._connection.has_pending_idle():
                self._connection.idle_done()
            yield from self._connection.logout()
        if self._idle_loop_task:
            self._idle_loop_task.cancel()

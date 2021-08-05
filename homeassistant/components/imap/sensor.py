"""IMAP sensor support."""
import asyncio
import logging

from aioimaplib import IMAP4_SSL, AioImapException
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SERVER = "server"
CONF_FOLDER = "folder"
CONF_SEARCH = "search"
CONF_CHARSET = "charset"

DEFAULT_PORT = 993

ICON = "mdi:email-outline"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SERVER): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_CHARSET, default="utf-8"): cv.string,
        vol.Optional(CONF_FOLDER, default="INBOX"): cv.string,
        vol.Optional(CONF_SEARCH, default="UnSeen UnDeleted"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the IMAP platform."""
    sensor = ImapSensor(
        config.get(CONF_NAME),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_SERVER),
        config.get(CONF_PORT),
        config.get(CONF_CHARSET),
        config.get(CONF_FOLDER),
        config.get(CONF_SEARCH),
    )
    if not await sensor.connection():
        raise PlatformNotReady

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.shutdown)
    async_add_entities([sensor], True)


class ImapSensor(SensorEntity):
    """Representation of an IMAP sensor."""

    def __init__(self, name, user, password, server, port, charset, folder, search):
        """Initialize the sensor."""
        self._name = name or user
        self._user = user
        self._password = password
        self._server = server
        self._port = port
        self._charset = charset
        self._folder = folder
        self._email_count = None
        self._search = search
        self._connection = None
        self._does_push = None
        self._idle_loop_task = None

    async def async_added_to_hass(self):
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
        """Return the number of emails found."""
        return self._email_count

    @property
    def available(self):
        """Return the availability of the device."""
        return self._connection is not None

    @property
    def should_poll(self):
        """Return if polling is needed."""
        return not self._does_push

    async def connection(self):
        """Return a connection to the server, establishing it if necessary."""
        if self._connection is None:
            try:
                self._connection = IMAP4_SSL(self._server, self._port)
                await self._connection.wait_hello_from_server()
                await self._connection.login(self._user, self._password)
                await self._connection.select(self._folder)
                self._does_push = self._connection.has_capability("IDLE")
            except (AioImapException, asyncio.TimeoutError):
                self._connection = None

        return self._connection

    async def idle_loop(self):
        """Wait for data pushed from server."""
        while True:
            try:
                if await self.connection():
                    await self.refresh_email_count()
                    self.async_write_ha_state()

                    idle = await self._connection.idle_start()
                    await self._connection.wait_server_push()
                    self._connection.idle_done()
                    with async_timeout.timeout(10):
                        await idle
                else:
                    self.async_write_ha_state()
            except (AioImapException, asyncio.TimeoutError):
                self.disconnected()

    async def async_update(self):
        """Periodic polling of state."""
        try:
            if await self.connection():
                await self.refresh_email_count()
        except (AioImapException, asyncio.TimeoutError):
            self.disconnected()

    async def refresh_email_count(self):
        """Check the number of found emails."""
        if self._connection:
            await self._connection.noop()
            result, lines = await self._connection.search(
                self._search, charset=self._charset
            )

            if result == "OK":
                self._email_count = len(lines[0].split())
            else:
                _LOGGER.error(
                    "Can't parse IMAP server response to search '%s':  %s / %s",
                    self._search,
                    result,
                    lines[0],
                )

    def disconnected(self):
        """Forget the connection after it was lost."""
        _LOGGER.warning("Lost %s (will attempt to reconnect)", self._server)
        self._connection = None

    async def shutdown(self, *_):
        """Close resources."""
        if self._connection:
            if self._connection.has_pending_idle():
                self._connection.idle_done()
            await self._connection.logout()
        if self._idle_loop_task:
            self._idle_loop_task.cancel()

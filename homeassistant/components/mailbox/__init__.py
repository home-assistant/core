"""Support for Voice mailboxes."""
import asyncio
from contextlib import suppress
from datetime import timedelta
import logging

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound
import async_timeout

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.setup import async_prepare_setup_platform

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mailbox"

EVENT = "mailbox_updated"
CONTENT_TYPE_MPEG = "audio/mpeg"
CONTENT_TYPE_NONE = "none"

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass, config):
    """Track states and offer events for mailboxes."""
    mailboxes = []
    hass.components.frontend.async_register_built_in_panel(
        "mailbox", "mailbox", "mdi:mailbox"
    )
    hass.http.register_view(MailboxPlatformsView(mailboxes))
    hass.http.register_view(MailboxMessageView(mailboxes))
    hass.http.register_view(MailboxMediaView(mailboxes))
    hass.http.register_view(MailboxDeleteView(mailboxes))

    async def async_setup_platform(p_type, p_config=None, discovery_info=None):
        """Set up a mailbox platform."""
        if p_config is None:
            p_config = {}
        if discovery_info is None:
            discovery_info = {}

        platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown mailbox platform specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)
        mailbox = None
        try:
            if hasattr(platform, "async_get_handler"):
                mailbox = await platform.async_get_handler(
                    hass, p_config, discovery_info
                )
            elif hasattr(platform, "get_handler"):
                mailbox = await hass.async_add_executor_job(
                    platform.get_handler, hass, p_config, discovery_info
                )
            else:
                raise HomeAssistantError("Invalid mailbox platform.")

            if mailbox is None:
                _LOGGER.error("Failed to initialize mailbox platform %s", p_type)
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform %s", p_type)
            return

        mailboxes.append(mailbox)
        mailbox_entity = MailboxEntity(mailbox)
        component = EntityComponent(
            logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
        )
        await component.async_add_entities([mailbox_entity])

    setup_tasks = [
        async_setup_platform(p_type, p_config)
        for p_type, p_config in config_per_platform(config, DOMAIN)
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(platform, info):
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True


class MailboxEntity(Entity):
    """Entity for each mailbox platform to provide a badge display."""

    def __init__(self, mailbox):
        """Initialize mailbox entity."""
        self.mailbox = mailbox
        self.message_count = 0

    async def async_added_to_hass(self):
        """Complete entity initialization."""

        @callback
        def _mailbox_updated(event):
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen(EVENT, _mailbox_updated)
        self.async_schedule_update_ha_state(True)

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return str(self.message_count)

    @property
    def name(self):
        """Return the name of the entity."""
        return self.mailbox.name

    async def async_update(self):
        """Retrieve messages from platform."""
        messages = await self.mailbox.async_get_messages()
        self.message_count = len(messages)


class Mailbox:
    """Represent a mailbox device."""

    def __init__(self, hass, name):
        """Initialize mailbox object."""
        self.hass = hass
        self.name = name

    @callback
    def async_update(self):
        """Send event notification of updated mailbox."""
        self.hass.bus.async_fire(EVENT)

    @property
    def media_type(self):
        """Return the supported media type."""
        raise NotImplementedError()

    @property
    def can_delete(self):
        """Return if messages can be deleted."""
        return False

    @property
    def has_media(self):
        """Return if messages have attached media files."""
        return False

    async def async_get_media(self, msgid):
        """Return the media blob for the msgid."""
        raise NotImplementedError()

    async def async_get_messages(self):
        """Return a list of the current messages."""
        raise NotImplementedError()

    async def async_delete(self, msgid):
        """Delete the specified messages."""
        raise NotImplementedError()


class StreamError(Exception):
    """Media streaming exception."""

    pass


class MailboxView(HomeAssistantView):
    """Base mailbox view."""

    def __init__(self, mailboxes):
        """Initialize a basic mailbox view."""
        self.mailboxes = mailboxes

    def get_mailbox(self, platform):
        """Retrieve the specified mailbox."""
        for mailbox in self.mailboxes:
            if mailbox.name == platform:
                return mailbox
        raise HTTPNotFound


class MailboxPlatformsView(MailboxView):
    """View to return the list of mailbox platforms."""

    url = "/api/mailbox/platforms"
    name = "api:mailbox:platforms"

    async def get(self, request):
        """Retrieve list of platforms."""
        platforms = []
        for mailbox in self.mailboxes:
            platforms.append(
                {
                    "name": mailbox.name,
                    "has_media": mailbox.has_media,
                    "can_delete": mailbox.can_delete,
                }
            )
        return self.json(platforms)


class MailboxMessageView(MailboxView):
    """View to return the list of messages."""

    url = "/api/mailbox/messages/{platform}"
    name = "api:mailbox:messages"

    async def get(self, request, platform):
        """Retrieve messages."""
        mailbox = self.get_mailbox(platform)
        messages = await mailbox.async_get_messages()
        return self.json(messages)


class MailboxDeleteView(MailboxView):
    """View to delete selected messages."""

    url = "/api/mailbox/delete/{platform}/{msgid}"
    name = "api:mailbox:delete"

    async def delete(self, request, platform, msgid):
        """Delete items."""
        mailbox = self.get_mailbox(platform)
        await mailbox.async_delete(msgid)


class MailboxMediaView(MailboxView):
    """View to return a media file."""

    url = r"/api/mailbox/media/{platform}/{msgid}"
    name = "api:asteriskmbox:media"

    async def get(self, request, platform, msgid):
        """Retrieve media."""
        mailbox = self.get_mailbox(platform)

        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10):
                try:
                    stream = await mailbox.async_get_media(msgid)
                except StreamError as err:
                    error_msg = "Error getting media: %s" % (err)
                    _LOGGER.error(error_msg)
                    return web.Response(status=500)
            if stream:
                return web.Response(body=stream, content_type=mailbox.media_type)

        return web.Response(status=500)

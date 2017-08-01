"""
Provides functionality for mailboxes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mailbox/
"""

import asyncio
import logging
from functools import partial
from contextlib import suppress
from datetime import timedelta

import async_timeout

from aiohttp import web

from homeassistant.const import (HTTP_BAD_REQUEST)

from homeassistant.core import callback
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_prepare_setup_platform


DOMAIN = 'mailbox'
EVENT = 'mailbox_updated'
CONTENT_TYPE_MPEG = 'audio/mpeg'
SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for mailboxes."""
    mailboxes = []
    hass.components.frontend.register_built_in_panel(
        'mailbox', 'Mailbox', 'mdi:account-location')
    hass.http.register_view(MailboxPlatformsView(mailboxes))
    hass.http.register_view(MailboxMessageView(mailboxes))
    hass.http.register_view(MailboxMediaView(mailboxes))
    hass.http.register_view(MailboxDeleteView(mailboxes))

    @asyncio.coroutine
    def async_setup_platform(p_type, p_config=None, discovery_info=None):
        """Set up a mailbox platform."""
        if p_config is None:
            p_config = {}
        if discovery_info is None:
            discovery_info = {}

        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown mailbox platform specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)
        mailbox = None
        try:
            if hasattr(platform, 'async_get_handler'):
                mailbox = yield from \
                    platform.async_get_handler(hass, p_config, discovery_info)
            elif hasattr(platform, 'get_handler'):
                mailbox = yield from hass.async_add_job(
                    platform.get_handler, hass, p_config, discovery_info)
            else:
                raise HomeAssistantError("Invalid mailbox platform.")

            if mailbox is None:
                _LOGGER.error(
                    "Failed to initialize mailbox platform %s", p_type)
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up platform %s', p_type)
            return

        mailboxes.append(mailbox)
        mailbox_entity = MailboxEntity(hass, mailbox)
        component = EntityComponent(
            logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)
        yield from component.async_add_entity(mailbox_entity)

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    @asyncio.coroutine
    def async_platform_discovered(platform, info):
        """Handle for discovered platform."""
        yield from async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True


class MailboxEntity(Entity):
    """Entity for each mailbox platform."""

    def __init__(self, hass, mailbox):
        """Initialize mailbox entity."""
        self.mailbox = mailbox
        self.hass = hass

        @callback
        def _mailbox_updated(event):
            self.hass.async_add_job(self.async_update_ha_state(True))

        hass.bus.async_listen(EVENT, _mailbox_updated)

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return str(len(self.mailbox.get_messages()))

    @property
    def name(self):
        """Return the name of the entity."""
        return self.mailbox.name


class Mailbox(object):
    """Represent an mailbox device."""

    def __init__(self, hass, name):
        """Initialize mailbox object."""
        self.hass = hass
        self.name = name

    def update(self):
        """Send event notification of updated mailbox."""
        self.hass.bus.async_fire(EVENT)

    def get_media_type(self):
        """Return the supported media type."""
        raise NotImplementedError()

    def get_media(self, msgid):
        """Return the media blob for the msgid."""
        raise NotImplementedError()

    def get_messages(self):
        """Return a list of the current messages."""
        raise NotImplementedError()

    def delete(self, msgids):
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
        return None


class MailboxPlatformsView(MailboxView):
    """View to return the list of mailbox platforms."""

    url = "/api/mailbox/platforms"
    name = "api:mailbox:platforms"

    @asyncio.coroutine
    def get(self, request):
        """Retrieve list of platforms."""
        platforms = []
        for mailbox in self.mailboxes:
            platforms.append(mailbox.name)
        return self.json(platforms)


class MailboxMessageView(MailboxView):
    """View to return the list of messages."""

    url = "/api/mailbox/messages/{platform}"
    name = "api:mailbox:messages"

    @asyncio.coroutine
    def get(self, request, platform):
        """Retrieve messages."""
        mailbox = self.get_mailbox(platform)
        if mailbox is None:
            return web.Response(status=401)
        return self.json(mailbox.get_messages())


class MailboxDeleteView(MailboxView):
    """View to delete selected messages."""

    url = "/api/mailbox/delete/{platform}"
    name = "api:mailbox:delete"

    @asyncio.coroutine
    def post(self, request, platform):
        """Delete items."""
        mailbox = self.get_mailbox(platform)
        if mailbox is None:
            return web.Response(status=401)
        try:
            data = yield from request.json()
            mailbox.delete(data)
        except ValueError:
            return self.json_message('Bad item id', HTTP_BAD_REQUEST)


class MailboxMediaView(MailboxView):
    """View to return a media file."""

    url = r"/api/mailbox/media/{platform}/{msgid}"
    name = "api:asteriskmbox:media"

    @asyncio.coroutine
    def get(self, request, platform, msgid):
        """Retrieve media."""
        mailbox = self.get_mailbox(platform)
        if mailbox is None:
            return web.Response(status=401)

        hass = request.app['hass']
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10, loop=hass.loop):
                try:
                    stream = yield from hass.async_add_job(
                        partial(mailbox.get_media, msgid))
                except StreamError as err:
                    error_msg = "Error getting media: %s" % (err)
                    _LOGGER.error(error_msg)
                    return web.Response(status=500)
            if stream:
                return web.Response(body=stream,
                                    content_type=mailbox.get_media_type)

        return web.Response(status=500)

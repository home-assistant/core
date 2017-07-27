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

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.components.http import HomeAssistantView


DOMAIN = 'mailbox'
SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for mailboxes."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    hass.components.frontend.register_built_in_panel(
        'mailbox', 'Mailbox', 'mdi:account-location')
    hass.http.register_view(MailboxMessageView(component.entities))
    hass.http.register_view(MailboxMediaView(component.entities))
    hass.http.register_view(MailboxDeleteView(component.entities))

    yield from component.async_setup(config)
    return True


class MailboxDevice(Entity):
    """Represent an mailbox device."""

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return str(len(self.get_messages()))

    @property
    def supports_delete(self):
        """Return whether deletion is supported."""
        return True

    @property
    def get_media_type(self):
        """Return the supported media type."""
        return None

    @classmethod
    def get_media(cls, msgid):
        """Return the media blob for the msgid."""
        return None

    def get_messages(self):
        """Return a list of the current messages."""
        raise NotImplementedError()

    @classmethod
    def delete(cls, msgids):
        """Delete the specified messages."""
        return False


class StreamError(Exception):
    """Media streaming exception."""

    pass


class MailboxView(HomeAssistantView):
    """Base mailbox view."""

    def __init__(self, entities):
        """Initialize a basic mailbox view."""
        self.entities = entities


class MailboxMessageView(MailboxView):
    """View to return the list of messages."""

    url = "/api/mailbox/messages/{entity_id}"
    name = "api:mailbox:messages"

    @asyncio.coroutine
    def get(self, request, entity_id):
        """Retrieve messages."""
        camera = self.entities.get(entity_id)
        if camera is None:
            return web.Response(status=401)
        return self.json(camera.get_messages())


class MailboxDeleteView(MailboxView):
    """View to delete selected messages."""

    url = "/api/mailbox/delete/{entity_id}"
    name = "api:mailbox:delete"

    @asyncio.coroutine
    def post(self, request, entity_id):
        """Delete items."""
        camera = self.entities.get(entity_id)
        if camera is None:
            return web.Response(status=401)
        try:
            data = yield from request.json()
            camera.delete(data)
        except ValueError:
            return self.json_message('Bad item id', HTTP_BAD_REQUEST)


class MailboxMediaView(MailboxView):
    """View to return a media file."""

    url = r"/api/mailbox/media/{entity_id}/{msgid}"
    name = "api:asteriskmbox:media"

    @asyncio.coroutine
    def get(self, request, entity_id, msgid):
        """Retrieve media."""
        camera = self.entities.get(entity_id)
        if camera is None:
            return web.Response(status=401)

        hass = request.app['hass']
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10, loop=hass.loop):
                try:
                    stream = yield from hass.async_add_job(
                        partial(camera.get_media, msgid))
                except StreamError as err:
                    error_msg = "Error getting media: %s" % (err)
                    _LOGGER.error(error_msg)
                    return web.Response(status=500)
            if stream:
                return web.Response(body=stream,
                                    content_type=camera.get_media_type)

        return web.Response(status=500)

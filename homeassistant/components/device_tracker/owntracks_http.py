"""
Device tracker platform that adds support for OwnTracks over HTTP.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.owntracks_http/
"""
import asyncio
import re

from aiohttp.web_exceptions import HTTPInternalServerError

from homeassistant.components.http import HomeAssistantView

# pylint: disable=unused-import
from .owntracks import (  # NOQA
    REQUIREMENTS, PLATFORM_SCHEMA, context_from_config, async_handle_message)


DEPENDENCIES = ['http']


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up an OwnTracks tracker."""
    context = context_from_config(async_see, config)

    hass.http.register_view(OwnTracksView(context))

    return True


class OwnTracksView(HomeAssistantView):
    """View to handle OwnTracks HTTP requests."""

    url = '/api/owntracks/{user}/{device}'
    name = 'api:owntracks'

    def __init__(self, context):
        """Initialize OwnTracks URL endpoints."""
        self.context = context

    @asyncio.coroutine
    def post(self, request, user, device):
        """Handle an OwnTracks message."""
        hass = request.app['hass']

        subscription = self.context.mqtt_topic
        topic = re.sub('/#$', '', subscription)

        message = yield from request.json()
        message['topic'] = '{}/{}/{}'.format(topic, user, device)

        try:
            yield from async_handle_message(hass, self.context, message)
            return self.json([])

        except ValueError:
            raise HTTPInternalServerError

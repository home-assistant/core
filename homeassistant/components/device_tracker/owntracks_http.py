"""
Device tracker platform that adds support for OwnTracks over HTTP.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.owntracks_http/
"""
import json
import logging
import re

from aiohttp.web import Response
import voluptuous as vol

# pylint: disable=unused-import
from homeassistant.components.device_tracker.owntracks import (  # NOQA
    PLATFORM_SCHEMA, REQUIREMENTS, async_handle_message, context_from_config)
from homeassistant.const import CONF_WEBHOOK_ID
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['webhook']

_LOGGER = logging.getLogger(__name__)

EVENT_RECEIVED = 'owntracks_http_webhook_received'
EVENT_RESPONSE = 'owntracks_http_webhook_response_'

DOMAIN = 'device_tracker.owntracks_http'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_WEBHOOK_ID): cv.string
})


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up OwnTracks HTTP component."""
    context = context_from_config(async_see, config)

    subscription = context.mqtt_topic
    topic = re.sub('/#$', '', subscription)

    async def handle_webhook(hass, webhook_id, request):
        """Handle webhook callback."""
        headers = request.headers
        data = dict()

        if 'X-Limit-U' in headers:
            data['user'] = headers['X-Limit-U']
        elif 'u' in request.query:
            data['user'] = request.query['u']
        else:
            return Response(
                body=json.dumps({'error': 'You need to supply username.'}),
                content_type="application/json"
            )

        if 'X-Limit-D' in headers:
            data['device'] = headers['X-Limit-D']
        elif 'd' in request.query:
            data['device'] = request.query['d']
        else:
            return Response(
                body=json.dumps({'error': 'You need to supply device name.'}),
                content_type="application/json"
            )

        message = await request.json()

        message['topic'] = '{}/{}/{}'.format(topic, data['user'],
                                             data['device'])

        try:
            await async_handle_message(hass, context, message)
            return Response(body=json.dumps([]), status=200,
                            content_type="application/json")
        except ValueError:
            _LOGGER.error("Received invalid JSON")
            return None

    hass.components.webhook.async_register(
        'owntracks', 'OwnTracks', config['webhook_id'], handle_webhook)

    return True

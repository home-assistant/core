"""Provides a Hue API to control Home Assistant."""
import asyncio
import logging

from aiohttp import web

from homeassistant import core
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON,
    STATE_OFF, HTTP_BAD_REQUEST, HTTP_NOT_FOUND,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_SUPPORTED_FEATURES, SUPPORT_BRIGHTNESS
)
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

ATTR_EMULATED_HUE = 'emulated_hue'
ATTR_EMULATED_HUE_NAME = 'emulated_hue_name'

HUE_API_STATE_ON = 'on'
HUE_API_STATE_BRI = 'bri'


class HueUsernameView(HomeAssistantView):
    """Handle requests to create a username for the emulated hue bridge."""

    url = '/api'
    name = 'emulated_hue:api:create_username'
    extra_urls = ['/api/']
    requires_auth = False

    @asyncio.coroutine
    def post(self, request):
        """Handle a POST request."""
        try:
            data = yield from request.json()
        except ValueError:
            return self.json_message('Invalid JSON', HTTP_BAD_REQUEST)

        if 'devicetype' not in data:
            return self.json_message('devicetype not specified',
                                     HTTP_BAD_REQUEST)

        return self.json([{'success': {'username': '12345678901234567890'}}])


class HueAllLightsStateView(HomeAssistantView):
    """Handle requests for getting and setting info about entities."""

    url = '/api/{username}/lights'
    name = 'emulated_hue:lights:state'
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request, username):
        """Process a request to get the list of available lights."""
        hass = request.app['hass']
        json_response = {}

        for entity in hass.states.async_all():
            if self.config.is_entity_exposed(entity):
                number = self.config.entity_id_to_number(entity.entity_id)
                json_response[number] = entity_to_json(entity)

        return self.json(json_response)


class HueOneLightStateView(HomeAssistantView):
    """Handle requests for getting and setting info about entities."""

    url = '/api/{username}/lights/{entity_id}'
    name = 'emulated_hue:light:state'
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request, username, entity_id=None):
        """Process a request to get the state of an individual light."""
        hass = request.app['hass']
        entity_id = self.config.number_to_entity_id(entity_id)
        entity = hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error('Entity not found: %s', entity_id)
            return web.Response(text="Entity not found", status=404)

        if not self.config.is_entity_exposed(entity):
            _LOGGER.error('Entity not exposed: %s', entity_id)
            return web.Response(text="Entity not exposed", status=404)

        cached_state = self.config.cached_states.get(entity_id, None)

        if cached_state is None:
            final_state = entity.state == STATE_ON
            final_brightness = entity.attributes.get(
                ATTR_BRIGHTNESS, 255 if final_state else 0)
        else:
            final_state, final_brightness = cached_state

        json_response = entity_to_json(entity, final_state, final_brightness)

        return self.json(json_response)


class HueOneLightChangeView(HomeAssistantView):
    """Handle requests for getting and setting info about entities."""

    url = '/api/{username}/lights/{entity_number}/state'
    name = 'emulated_hue:light:state'
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @asyncio.coroutine
    def put(self, request, username, entity_number):
        """Process a request to set the state of an individual light."""
        config = self.config
        hass = request.app['hass']
        entity_id = config.number_to_entity_id(entity_number)

        if entity_id is None:
            _LOGGER.error('Unknown entity number: %s', entity_number)
            return self.json_message('Entity not found', HTTP_NOT_FOUND)

        entity = hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error('Entity not found: %s', entity_id)
            return self.json_message('Entity not found', HTTP_NOT_FOUND)

        if not config.is_entity_exposed(entity):
            _LOGGER.error('Entity not exposed: %s', entity_id)
            return web.Response(text="Entity not exposed", status=404)

        try:
            request_json = yield from request.json()
        except ValueError:
            _LOGGER.error('Received invalid json')
            return self.json_message('Invalid JSON', HTTP_BAD_REQUEST)

        # Parse the request into requested "on" status and brightness
        parsed = parse_hue_api_put_light_body(request_json, entity)

        if parsed is None:
            _LOGGER.error('Unable to parse data: %s', request_json)
            return web.Response(text="Bad request", status=400)

        result, brightness = parsed

        # Convert the resulting "on" status into the service we need to call
        service = SERVICE_TURN_ON if result else SERVICE_TURN_OFF

        # Construct what we need to send to the service
        data = {ATTR_ENTITY_ID: entity_id}

        # If the requested entity is a script add some variables
        if entity.domain == "script":
            data['variables'] = {
                'requested_state': STATE_ON if result else STATE_OFF
            }

            if brightness is not None:
                data['variables']['requested_level'] = brightness

        elif brightness is not None:
            data[ATTR_BRIGHTNESS] = brightness

        if entity.domain in config.off_maps_to_on_domains:
            # Map the off command to on
            service = SERVICE_TURN_ON

            # Caching is required because things like scripts and scenes won't
            # report as "off" to Alexa if an "off" command is received, because
            # they'll map to "on". Thus, instead of reporting its actual
            # status, we report what Alexa will want to see, which is the same
            # as the actual requested command.
            config.cached_states[entity_id] = (result, brightness)

        # Perform the requested action
        yield from hass.services.async_call(core.DOMAIN, service, data,
                                            blocking=True)

        json_response = \
            [create_hue_success_response(entity_id, HUE_API_STATE_ON, result)]

        if brightness is not None:
            json_response.append(create_hue_success_response(
                entity_id, HUE_API_STATE_BRI, brightness))

        return self.json(json_response)


def parse_hue_api_put_light_body(request_json, entity):
    """Parse the body of a request to change the state of a light."""
    if HUE_API_STATE_ON in request_json:
        if not isinstance(request_json[HUE_API_STATE_ON], bool):
            return None

        if request_json['on']:
            # Echo requested device be turned on
            brightness = None
            report_brightness = False
            result = True
        else:
            # Echo requested device be turned off
            brightness = None
            report_brightness = False
            result = False

    if HUE_API_STATE_BRI in request_json:
        # Make sure the entity actually supports brightness
        entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if (entity_features & SUPPORT_BRIGHTNESS) == SUPPORT_BRIGHTNESS:
            try:
                # Clamp brightness from 0 to 255
                brightness = \
                    max(0, min(int(request_json[HUE_API_STATE_BRI]), 255))
            except ValueError:
                return None

            report_brightness = True
            result = (brightness > 0)
        elif entity.domain.lower() == "script":
            # Convert 0-255 to 0-100
            level = int(request_json[HUE_API_STATE_BRI]) / 255 * 100

            brightness = round(level)
            report_brightness = True
            result = True

    return (result, brightness) if report_brightness else (result, None)


def entity_to_json(entity, is_on=None, brightness=None):
    """Convert an entity to its Hue bridge JSON representation."""
    if is_on is None:
        is_on = entity.state == STATE_ON

    if brightness is None:
        brightness = 255 if is_on else 0

    name = entity.attributes.get(ATTR_EMULATED_HUE_NAME, entity.name)

    return {
        'state':
        {
            HUE_API_STATE_ON: is_on,
            HUE_API_STATE_BRI: brightness,
            'reachable': True
        },
        'type': 'Dimmable light',
        'name': name,
        'modelid': 'HASS123',
        'uniqueid': entity.entity_id,
        'swversion': '123'
    }


def create_hue_success_response(entity_id, attr, value):
    """Create a success response for an attribute set on a light."""
    success_key = '/lights/{}/state/{}'.format(entity_id, attr)
    return {'success': {success_key: value}}

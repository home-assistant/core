"""Support for alexa Smart Home Skill API."""
import asyncio
import logging
from uuid import uuid4

from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF)
from homeassistant.components import switch, light
from homeassistant.util.decorator import Registry

HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)

API_DIRECTIVE = 'directive'
API_EVENT = 'event'
API_HEADER = 'header'
API_PAYLOAD = 'payload'
API_ENDPOINT = 'endpoint'


MAPPING_COMPONENT = {
    switch.DOMAIN: ['SWITCH', ('Alexa.PowerController',), None],
    light.DOMAIN: [
        'LIGHT', ('Alexa.PowerController',), {
            light.SUPPORT_BRIGHTNESS: 'Alexa.BrightnessController'
        }
    ],
}


@asyncio.coroutine
def async_handle_message(hass, message):
    """Handle incoming API messages."""
    assert message[API_DIRECTIVE][API_HEADER]['payloadVersion'] == '3'

    # Read head data
    message = message[API_DIRECTIVE]
    namespace = message[API_HEADER]['namespace']
    name = message[API_HEADER]['name']

    # Do we support this API request?
    funct_ref = HANDLERS.get((namespace, name))
    if not funct_ref:
        _LOGGER.warning(
            "Unsupported API request %s/%s", namespace, name)
        return api_error(message)

    return (yield from funct_ref(hass, message))


def api_message(request, name='Response', namespace='Alexa', payload=None):
    """Create a API formatted response message.

    Async friendly.
    """
    payload = payload or {}

    response = {
        API_EVENT: {
            API_HEADER: {
                'namespace': namespace,
                'name': name,
                'messageId': str(uuid4()),
                'payloadVersion': '3',
            },
            API_PAYLOAD: payload,
        }
    }

    # If a correlation token exsits, add it to header / Need by Async requests
    token = request[API_HEADER].get('correlationToken')
    if token:
        response[API_EVENT][API_HEADER]['correlationToken'] = token

    # Extend event with endpoint object / Need by Async requests
    if API_ENDPOINT in request:
        response[API_EVENT][API_ENDPOINT] = request[API_ENDPOINT].copy()

    return response


def api_error(request, error_type='INTERNAL_ERROR', error_message=""):
    """Create a API formatted error response.

    Async friendly.
    """
    payload = {
        'type': error_type,
        'message': error_message,
    }

    return api_message(request, name='ErrorResponse', payload=payload)


@HANDLERS.register(('Alexa.Discovery', 'Discover'))
@asyncio.coroutine
def async_api_discovery(hass, request):
    """Create a API formatted discovery response.

    Async friendly.
    """
    discovery_endpoints = []

    for entity in hass.states.async_all():
        class_data = MAPPING_COMPONENT.get(entity.domain)

        if not class_data:
            continue

        endpoint = {
            'displayCategories': [class_data[0]],
            'additionalApplianceDetails': {},
            'endpointId': entity.entity_id.replace('.', '#'),
            'friendlyName': entity.name,
            'description': '',
            'manufacturerName': 'Unknown',
        }
        actions = set()

        # static actions
        if class_data[1]:
            actions |= set(class_data[1])

        # dynamic actions
        if class_data[2]:
            supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            for feature, action_name in class_data[2].items():
                if feature & supported > 0:
                    actions.add(action_name)

        # Write action into capabilities
        capabilities = []
        for action in actions:
            capabilities.append({
                'type': 'AlexaInterface',
                'interface': action,
                'version': 3,
            })

        endpoint['capabilities'] = capabilities
        discovery_endpoints.append(endpoint)

    return api_message(
        request, name='Discover.Response', namespace='Alexa.Discovery',
        payload={'endpoints': discovery_endpoints})


def extract_entity(funct):
    """Decorator for extract entity object from request."""
    @asyncio.coroutine
    def async_api_entity_wrapper(hass, request):
        """Process a turn on request."""
        entity_id = request[API_ENDPOINT]['endpointId'].replace('#', '.')

        # extract state object
        entity = hass.states.get(entity_id)
        if not entity:
            _LOGGER.error("Can't process %s for %s",
                          request[API_HEADER]['name'], entity_id)
            return api_error(request, error_type='NO_SUCH_ENDPOINT')

        return (yield from funct(hass, request, entity))

    return async_api_entity_wrapper


@HANDLERS.register(('Alexa.PowerController', 'TurnOn'))
@extract_entity
@asyncio.coroutine
def async_api_turn_on(hass, request, entity):
    """Process a turn on request."""
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PowerController', 'TurnOff'))
@extract_entity
@asyncio.coroutine
def async_api_turn_off(hass, request, entity):
    """Process a turn off request."""
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_OFF, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.BrightnessController', 'SetBrightness'))
@extract_entity
@asyncio.coroutine
def async_api_set_brightness(hass, request, entity):
    """Process a set brightness request."""
    brightness = request[API_PAYLOAD]['brightness']

    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_BRIGHTNESS: brightness,
    }, blocking=True)

    return api_message(request)

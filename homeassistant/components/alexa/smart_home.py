"""Support for alexa Smart Home Skill API."""
import asyncio
import logging
from uuid import uuid4

from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_SUPPORTED_FEATURES, ATTR_ENTITY_ID,
    SERVICE_TURN_ON, SERVICE_TURN_OFF)
from homeassistant.components import switch, light

_LOGGER = logging.getLogger(__name__)

ATTR_HEADER = 'header'
ATTR_NAME = 'name'
ATTR_NAMESPACE = 'namespace'
ATTR_MESSAGE_ID = 'messageId'
ATTR_PAYLOAD = 'payload'
ATTR_PAYLOAD_VERSION = 'payloadVersion'


MAPPING_API = {
    'DiscoverAppliancesRequest': async_api_discovery,
    'TurnOnRequest': async_api_turn_on,
    'TurnOffRequest': async_api_turn_off,
    'SetPercentageRequest': async_api_set_brightness,
}

MAPPING_COMPONENT = {
    switch.DOMAIN: ['SWITCH', ('turnOff', 'turnOn'), None],
    light.DOMAIN: [
        'LIGHT', ('turnOff', 'turnOn'), {
            light.SUPPORT_BRIGHTNESS: 'setPercentage'
        }
    ],
}


@asyncio.coroutine
def handle_message(hass, message):
    """Handle incomming API messages."""
    assert message[ATTR_HEADER][ATTR_PAYLOAD_VERSION] == 2

    # Do we support this API request?
    funct_name = message[ATTR_HEADER][ATTR_NAME]
    if funct_name not in MAPPING_API:
        _LOGGER.warning("Unsupported API request %s", funct_name)
        return api_error(message)

    return (yield from MAPPING_API[funct_name](hass, message))


def api_message(name, namespace, payload=None):
    """Create a API formated response message.

    Async friendly.
    """
    payload = payload or {}
    return {
        ATTR_HEADER: {
            ATTR_MESSAGE_ID: uuid4(),
            ATTR_NAME: name,
            ATTR_NAMESPACE: namespace,
            ATTR_PAYLOAD_VERSION: '2',
        },
        ATTR_PAYLOAD: payload,
    }


def api_error(request, exc='DriverInternalError'):
    """Create a API formated error response.

    Async friendly.
    """
    return api_message(exc, request[ATTR_HEADER][ATTR_NAMESPACE])


@asyncio.coroutine
def async_api_discovery(hass, request):
    """Create a API formated discovery response.

    Async friendly.
    """
    discovered_appliances = []

    for domain, class_data in MAPPING_COMPONENT.items():
        for entity in async_hass.states.entity_ids(domain_filter=domain):
            appliance = {
                'actions': [],
                'applianceTypes': [class_data[0]],
                'additionalApplianceDetails': {},
                'applianceId': entity.entity_id.replace('.', '#'),
                'friendlyDescription': '',
                'friendlyName': entity.attributes.get(ATTR_FRIENDLY_NAME, ''),
                'isReachable': True,
                'manufacturerName': 'Unknown',
                'modelName': 'Unknown',
                'version': 'Unknown',
            }

            # static actions
            if class_data[1]:
                appliance['actions'].extend(list(class_data[1]))

            # dynamic actions
            if class_data[2]:
                supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
                for feature, action_name in class_data[2].items():
                    if feature & supported > 0:
                        appliance['actions'].append(action_name)

            discovered_appliances.append(appliance)

    return api_message(
        'DiscoverAppliancesResponse', 'Alexa.ConnectedHome.Discovery',
        payload={'discoveredAppliances': discovered_appliances})


def extract_entity(funct):
    """Decorator for extract entity object from request."""
    @asyncio.coroutine
    def async_api_entity_wrapper(hass, request):
        """Process a turn on request."""
        entity_id = \
            request[ATTR_PAYLOAD]['appliance']['applianceId'].replace('#', '.')

        # extract state object
        entity = hass.states.get(entity_id)
        if not entity:
            _LOGGER.error("Can't process %s for %s",
                          request[ATTR_HEADER][ATTR_NAME], entity_id)
            return api_error(request)

        return (yield from funct(hass, request, entity))

    return async_api_entity_wrapper


@extract_entity
@asyncio.coroutine
def async_api_turn_on(hass, request, entity):
    """Process a turn on request."""
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message('TurnOnConfirmation', 'Alexa.ConnectedHome.Control')


@extract_entity
@asyncio.coroutine
def async_api_turn_off(hass, request, entity):
    """Process a turn off request."""
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_OFF, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message('TurnOffConfirmation', 'Alexa.ConnectedHome.Control')


@extract_entity
@asyncio.coroutine
def async_api_set_brightness(hass, request, entity):
    """Process a set percentage request."""
    brightness = request[ATTR_PAYLOAD]['percentageState']['value']
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_BRIGHTNESS: brightness,
    }, blocking=True)

    return api_message(
        'SetPercentageConfirmation', 'Alexa.ConnectedHome.Control')

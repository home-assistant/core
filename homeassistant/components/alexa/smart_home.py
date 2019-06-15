"""Support for alexa Smart Home Skill API."""
import logging

import homeassistant.core as ha

from .const import API_DIRECTIVE, API_HEADER
from .errors import (
    AlexaError,
    AlexaBridgeUnreachableError,
)
from .handlers import HANDLERS
from .messages import AlexaDirective

_LOGGER = logging.getLogger(__name__)

EVENT_ALEXA_SMART_HOME = 'alexa_smart_home'


# def _capability(interface,
#                 version=3,
#                 supports_deactivation=None,
#                 retrievable=None,
#                 properties_supported=None,
#                 cap_type='AlexaInterface'):
#     """Return a Smart Home API capability object.

#     https://developer.amazon.com/docs/device-apis/alexa-discovery.html#capability-object

#     There are some additional fields allowed but not implemented here since
#     we've no use case for them yet:

#       - proactively_reported

#     `supports_deactivation` applies only to scenes.
#     """
#     result = {
#         'type': cap_type,
#         'interface': interface,
#         'version': version,
#     }

#     if supports_deactivation is not None:
#         result['supportsDeactivation'] = supports_deactivation

#     if retrievable is not None:
#         result['retrievable'] = retrievable

#     if properties_supported is not None:
#         result['properties'] = {'supported': properties_supported}

#     return result


async def async_handle_message(
        hass,
        config,
        request,
        context=None,
        enabled=True,
):
    """Handle incoming API messages.

    If enabled is False, the response to all messagess will be a
    BRIDGE_UNREACHABLE error. This can be used if the API has been disabled in
    configuration.
    """
    assert request[API_DIRECTIVE][API_HEADER]['payloadVersion'] == '3'

    if context is None:
        context = ha.Context()

    directive = AlexaDirective(request)

    try:
        if not enabled:
            raise AlexaBridgeUnreachableError(
                'Alexa API not enabled in Home Assistant configuration')

        if directive.has_endpoint:
            directive.load_entity(hass, config)

        funct_ref = HANDLERS.get((directive.namespace, directive.name))
        if funct_ref:
            response = await funct_ref(hass, config, directive, context)
            if directive.has_endpoint:
                response.merge_context_properties(directive.endpoint)
        else:
            _LOGGER.warning(
                "Unsupported API request %s/%s",
                directive.namespace,
                directive.name,
            )
            response = directive.error()
    except AlexaError as err:
        response = directive.error(
            error_type=err.error_type,
            error_message=err.error_message)

    request_info = {
        'namespace': directive.namespace,
        'name': directive.name,
    }

    if directive.has_endpoint:
        request_info['entity_id'] = directive.entity_id

    hass.bus.async_fire(EVENT_ALEXA_SMART_HOME, {
        'request': request_info,
        'response': {
            'namespace': response.namespace,
            'name': response.name,
        }
    }, context=context)

    return response.serialize()

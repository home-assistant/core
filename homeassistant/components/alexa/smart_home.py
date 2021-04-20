"""Support for alexa Smart Home Skill API."""
import logging

import homeassistant.core as ha

from .const import API_DIRECTIVE, API_HEADER, EVENT_ALEXA_SMART_HOME
from .errors import AlexaBridgeUnreachableError, AlexaError
from .handlers import HANDLERS
from .messages import AlexaDirective

_LOGGER = logging.getLogger(__name__)


async def async_handle_message(hass, config, request, context=None, enabled=True):
    """Handle incoming API messages.

    If enabled is False, the response to all messagess will be a
    BRIDGE_UNREACHABLE error. This can be used if the API has been disabled in
    configuration.
    """
    assert request[API_DIRECTIVE][API_HEADER]["payloadVersion"] == "3"

    if context is None:
        context = ha.Context()

    directive = AlexaDirective(request)

    try:
        if not enabled:
            raise AlexaBridgeUnreachableError(
                "Alexa API not enabled in Home Assistant configuration"
            )

        if directive.has_endpoint:
            directive.load_entity(hass, config)

        funct_ref = HANDLERS.get((directive.namespace, directive.name))
        if funct_ref:
            response = await funct_ref(hass, config, directive, context)
            if directive.has_endpoint:
                response.merge_context_properties(directive.endpoint)
        else:
            _LOGGER.warning(
                "Unsupported API request %s/%s", directive.namespace, directive.name
            )
            response = directive.error()
    except AlexaError as err:
        response = directive.error(
            error_type=err.error_type, error_message=err.error_message
        )

    request_info = {"namespace": directive.namespace, "name": directive.name}

    if directive.has_endpoint:
        request_info["entity_id"] = directive.entity_id

    hass.bus.async_fire(
        EVENT_ALEXA_SMART_HOME,
        {
            "request": request_info,
            "response": {"namespace": response.namespace, "name": response.name},
        },
        context=context,
    )

    return response.serialize()

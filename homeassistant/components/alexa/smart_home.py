"""Support for alexa Smart Home Skill API."""
import asyncio
import logging
from uuid import uuid4

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
    """Create a API formated message.

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
    """Create a API formated error message.

    Async friendly.
    """
    return api_message(exc, request[ATTR_HEADER][ATTR_NAMESPACE])

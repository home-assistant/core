"""Support for alexa Smart Home Skill API."""
import asyncio
import logging
from uuid import uuid4

_LOGGER = logging.getLogger(__name__)

ATTR_NAME = 'name'
ATTR_HEADER = 'header'
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
        return api_error()

    return (yield from MAPPING_API[funct_name](hass, message))

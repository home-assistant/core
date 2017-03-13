"""
Component to receive telegram messages.

Either by polling or webhook.
"""

import asyncio
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PLATFORM, CONF_API_KEY

from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'telegram_bot'

_LOGGER = logging.getLogger(__name__)

EVENT_TELEGRAM_COMMAND = 'telegram_command'
EVENT_TELEGRAM_TEXT = 'telegram_text'

ATTR_COMMAND = 'command'
ATTR_USER_ID = 'user_id'
ATTR_ARGS = 'args'
ATTR_FROM_FIRST = 'from_first'
ATTR_FROM_LAST = 'from_last'
ATTR_TEXT = 'text'

CONF_ALLOWED_CHAT_IDS = 'allowed_chat_ids'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ALLOWED_CHAT_IDS): vol.All(cv.ensure_list,
                                                 [cv.positive_int])
}, extra=vol.ALLOW_EXTRA)


class WrongMessageException(Exception):
    """Exception to raise when an incoming message has wrong format."""

    pass


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    yield from component.async_setup(config)
    return True


@asyncio.coroutine
def process_message(data, allowed_chat_ids):
    """Check for basic message rules and prepare an event to be fired."""
    data = data.get('message')

    if (not data
            or 'from' not in data
            or 'text' not in data
            or data['from'].get('id') not in allowed_chat_ids):
        # Message is not correct.
        _LOGGER.error("Incoming message does not have required data.")
        return None, None

    event_data = {
        ATTR_USER_ID: data['from']['id'],
        ATTR_FROM_FIRST: data['from']['first_name'],
        ATTR_FROM_LAST: data['from']['last_name']}

    if data['text'][0] == '/':
        pieces = data['text'].split(' ')
        event_data[ATTR_COMMAND] = pieces[0]
        event_data[ATTR_ARGS] = pieces[1:]

        return (EVENT_TELEGRAM_COMMAND, event_data)

    else:
        event_data[ATTR_TEXT] = data['text']

        return (EVENT_TELEGRAM_TEXT, event_data)

# class BotReceiver:
#     """Base receiver class."""
#
#     def __init__(self, user_ids):
#         """Initialize the instance."""
#         self.allowed_chat_ids = user_ids
#         _LOGGER.debug("users allowed: %s", self.allowed_chat_ids)
#
#     @asyncio.coroutine
#     def process_message(self, data):
#         """Check for basic message rules and prepare an event to be fired."""
#         data = data.get('message')
#
#         if (not data
#             or 'from' not in data
#             or 'text' not in data
#             or data['from'].get('id') not in self.allowed_chat_ids):
#             # Message is not correct.
#             _LOGGER.error("Incoming message does not have required data.")
#             raise WrongMessageException()
#
#         event_data = {
#             ATTR_USER_ID: data['from']['id'],
#             ATTR_FROM_FIRST: data['from']['first_name'],
#             ATTR_FROM_LAST: data['from']['last_name']}
#
#         if data['text'][0] == '/':
#             pieces = data['text'].split(' ')
#             event_data[ATTR_COMMAND] = pieces[0]
#             event_data[ATTR_ARGS] = pieces[1:]
#
#             return (EVENT_TELEGRAM_COMMAND, event_data)
#
#         else:
#             event_data[ATTR_TEXT] = data['text']
#
#             return (EVENT_TELEGRAM_TEXT, event_data)

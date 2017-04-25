"""
Component to receive telegram messages, including callback queries.

Either by polling or webhook.
"""

import asyncio
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PLATFORM, CONF_API_KEY
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery, config_per_platform
from homeassistant.setup import async_prepare_setup_platform

DOMAIN = 'telegram_bot'

_LOGGER = logging.getLogger(__name__)

EVENT_TELEGRAM_COMMAND = 'telegram_command'
EVENT_TELEGRAM_TEXT = 'telegram_text'
EVENT_TELEGRAM_CALLBACK = 'telegram_callback'

ATTR_COMMAND = 'command'
ATTR_USER_ID = 'user_id'
ATTR_ARGS = 'args'
ATTR_DATA = 'data'
ATTR_MSG = 'message'
ATTR_CALLBACK_QUERY = 'callback_query'
ATTR_CHAT_INSTANCE = 'chat_instance'
ATTR_MSGID = 'id'
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


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the telegram bot component."""
    @asyncio.coroutine
    def async_setup_platform(p_type, p_config=None, discovery_info=None):
        """Setup a telegram bot platform."""
        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown notification service specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)

        try:
            if hasattr(platform, 'async_setup_platform'):
                notify_service = yield from \
                    platform.async_setup_platform(hass, p_config,
                                                  discovery_info)
            elif hasattr(platform, 'setup_platform'):
                notify_service = yield from hass.loop.run_in_executor(
                    None, platform.setup_platform, hass, p_config,
                    discovery_info)
            else:
                raise HomeAssistantError("Invalid telegram bot platform.")

            if notify_service is None:
                _LOGGER.error(
                    "Failed to initialize telegram bot %s", p_type)
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up platform %s', p_type)
            return

        return True

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    @asyncio.coroutine
    def async_platform_discovered(platform, info):
        """Callback to load a platform."""
        yield from async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True


class BaseTelegramBotEntity:
    """The base class for the telegram bot."""

    def __init__(self, hass, allowed_chat_ids):
        """Initialize the bot base class."""
        self.allowed_chat_ids = allowed_chat_ids
        self.hass = hass

    def _get_message_data(self, msg_data):
        if (not msg_data or ('text' not in msg_data
                             and 'data' not in msg_data) or
                'from' not in msg_data or
                msg_data['from'].get('id') not in self.allowed_chat_ids):
            # Message is not correct.
            _LOGGER.error("Incoming message does not have required data (%s)",
                          msg_data)
            return None
        return {
            ATTR_USER_ID: msg_data['from']['id'],
            ATTR_FROM_FIRST: msg_data['from']['first_name'],
            ATTR_FROM_LAST: msg_data['from']['last_name']}

    def process_message(self, data):
        """Check for basic message rules and fire an event if message is ok."""
        if ATTR_MSG in data:
            event = EVENT_TELEGRAM_COMMAND
            data = data.get(ATTR_MSG)
            event_data = self._get_message_data(data)
            if event_data is None:
                return False

            if data['text'][0] == '/':
                pieces = data['text'].split(' ')
                event_data[ATTR_COMMAND] = pieces[0]
                event_data[ATTR_ARGS] = pieces[1:]
            else:
                event_data[ATTR_TEXT] = data['text']
                event = EVENT_TELEGRAM_TEXT

            self.hass.bus.async_fire(event, event_data)
            return True
        elif ATTR_CALLBACK_QUERY in data:
            event = EVENT_TELEGRAM_CALLBACK
            data = data.get('callback_query')
            event_data = self._get_message_data(data)
            if event_data is None:
                return False

            event_data[ATTR_DATA] = data[ATTR_DATA]
            event_data[ATTR_MSG] = data[ATTR_MSG]
            event_data[ATTR_CHAT_INSTANCE] = data[ATTR_CHAT_INSTANCE]
            event_data[ATTR_MSGID] = data[ATTR_MSGID]

            self.hass.bus.async_fire(event, event_data)
            return True
        else:
            # Some other thing...
            _LOGGER.warning('SOME OTHER THING RECEIVED --> "%s"', data)
            return False

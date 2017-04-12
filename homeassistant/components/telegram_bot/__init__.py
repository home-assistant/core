"""
Component to receive telegram messages.

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

        _LOGGER.info("Setting up1 %s.%s", DOMAIN, p_type)

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

    def process_message(self, data):
        """Check for basic message rules and fire an event if message is ok."""
        data = data.get('message')

        if (not data
                or 'from' not in data
                or 'text' not in data
                or data['from'].get('id') not in self.allowed_chat_ids):
            # Message is not correct.
            _LOGGER.error("Incoming message does not have required data.")
            return False

        event = EVENT_TELEGRAM_COMMAND
        event_data = {
            ATTR_USER_ID: data['from']['id'],
            ATTR_FROM_FIRST: data['from']['first_name'],
            ATTR_FROM_LAST: data['from']['last_name']}

        if data['text'][0] == '/':
            pieces = data['text'].split(' ')
            event_data[ATTR_COMMAND] = pieces[0]
            event_data[ATTR_ARGS] = pieces[1:]

        else:
            event_data[ATTR_TEXT] = data['text']
            event = EVENT_TELEGRAM_TEXT

        self.hass.bus.async_fire(event, event_data)

        return True

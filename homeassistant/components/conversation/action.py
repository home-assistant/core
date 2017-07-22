"""
Support for functionality to have conversations with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""

import asyncio
import logging
import re

import voluptuous as vol

from homeassistant.components.conversation import (ConversationEngine,
                                                   PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import script

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = []

CONF_ACTION = 'action'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACTION): cv.SCRIPT_SCHEMA,
})


@asyncio.coroutine
def async_get_engine(hass, config):
    """Set up a simple textfile conversation component."""
    return ActionProvider(hass, config)


class ActionProvider(ConversationEngine):
    """Action conversation component."""

    def __init__(self, hass, config):
        """Init Action conversation provider."""
        super().__init__(hass)
        self.name = 'action'

        self.config = config
        self.action = config[CONF_ACTION]

    @asyncio.coroutine
    def process(self, text):
        """Call a config-defined action for processing of the text."""

        # Ignore empty text
        if not text or not text.strip():
            return

        _LOGGER.info("Conversation query: %s", (text))

        # Run action script
        parameters = {'text': text}
        si = script.Script(self.hass, self.action,
                           "Conversation action: {}".format(self.action))

        self.hass.async_add_job(si.async_run(parameters))

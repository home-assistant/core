"""
Support for command line covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.command_line/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.conversation import (ConversationEngine,
                                                   PLATFORM_SCHEMA)
from homeassistant.const import (CONF_PATH)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

TEXTFILE_SCHEMA = vol.Schema({
    vol.Required(CONF_PATH): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
})


@asyncio.coroutine
def async_get_engine(hass, config):
    """Set up a simple textfile conversation component."""
    return TextfileProvider(hass, config[CONF_PATH])


class TextfileProvider(ConversationEngine):
    """Textfile conversation component. Simply writes each text to a file."""

    def __init__(self, hass, path):
        """Init Textfile conversation provider."""
        super().__init__(hass)
        self.name = 'textfile'
        self.path = path

        _LOGGER.info("Initialized Conversation TextfileProvider (path: %s)",
                     self.path)

    @asyncio.coroutine
    def process(self, text):
        """Write text to file."""
        try:
            with open(self.path, "a") as f:
                f.write(text + "\n")

        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Could not write conversation text to file '%s': %s",
                          self.path, e)

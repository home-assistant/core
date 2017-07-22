"""
Support for functionality to have conversations with Home Assistant.

This component provides a service that accepts text as input, usually
natural language text that has been received via voice recognition or
remote chat.

This component purpose is to respond to input text.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.setup import async_prepare_setup_platform
from homeassistant.config import load_yaml_config_file
from homeassistant.helpers import config_per_platform
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = []

DOMAIN = 'conversation'
DEPENDENCIES = []

_LOGGER = logging.getLogger(__name__)

SERVICE_PROCESS = 'process'

ATTR_TEXT = 'text'

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
})

SCHEMA_SERVICE_PROCESS = vol.Schema({
    vol.Required(ATTR_TEXT): cv.string,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the conversation platform from configuration."""

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    @asyncio.coroutine
    def async_setup_platform(p_type, p_config, disc_info=None):
        """Set up a conversation platform."""
        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)
        if platform is None:
            return

        try:
            provider = yield from platform.async_get_engine(hass, p_config)

            if provider is None:
                _LOGGER.error("Error setting up platform %s", p_type)
                return

        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform %s: %s", p_type, ex)
            return

        @asyncio.coroutine
        def async_process_handle(service):
            """Service handle for say."""
            text = service.data.get(ATTR_TEXT)
            yield from provider.process(text)

        hass.services.async_register(
            DOMAIN, SERVICE_PROCESS, async_process_handle,
            descriptions.get(SERVICE_PROCESS), schema=SCHEMA_SERVICE_PROCESS)

    setup_tasks = [async_setup_platform(p_type, p_config)
                   for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    return True


class ConversationEngine(object):
    """Representation of a conversation engine."""

    hass = None
    name = None

    def __init__(self, hass):
        """Initialize a speech store."""
        self.hass = hass

    @asyncio.coroutine
    def process(self, text):
        """Process the given message."""
        raise NotImplementedError()

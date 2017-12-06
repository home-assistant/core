"""
Discord platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.discord/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService, ATTR_TARGET)
from homeassistant.const import CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['discord.py==0.16.12']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string
})


def get_service(hass, config, discovery_info=None):
    """Get the Discord notification service."""
    token = config.get(CONF_TOKEN)
    return DiscordNotificationService(hass, token)


class DiscordNotificationService(BaseNotificationService):
    """Implement the notification service for Discord."""

    def __init__(self, hass, token):
        """Initialize the service."""
        self.token = token
        self.hass = hass

    @asyncio.coroutine
    def async_send_message(self, message, **kwargs):
        """Login to Discord, send message to channel(s) and log out."""
        import discord
        discord_bot = discord.Client(loop=self.hass.loop)

        if ATTR_TARGET not in kwargs:
            _LOGGER.error("No target specified")
            return None

        # pylint: disable=unused-variable
        @discord_bot.event
        @asyncio.coroutine
        def on_ready():
            """Send the messages when the bot is ready."""
            try:
                for channelid in kwargs[ATTR_TARGET]:
                    channel = discord.Object(id=channelid)
                    yield from discord_bot.send_message(channel, message)
            except (discord.errors.HTTPException,
                    discord.errors.NotFound) as error:
                _LOGGER.warning("Communication error: %s", error)
            yield from discord_bot.logout()
            yield from discord_bot.close()

        yield from discord_bot.start(self.token)

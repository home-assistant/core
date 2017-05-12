"""
Discord platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.discord/
"""
import logging
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService, ATTR_TARGET)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['discord.py==0.16.0']

CONF_TOKEN = 'token'

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

        @discord_bot.event
        @asyncio.coroutine
        def on_ready():  # pylint: disable=unused-variable
            """Send the messages when the bot is ready."""
            for channelid in kwargs[ATTR_TARGET]:
                channel = discord.Object(id=channelid)
                yield from discord_bot.send_message(channel, message)
            yield from discord_bot.logout()
            yield from discord_bot.close()

        yield from discord_bot.start(self.token)

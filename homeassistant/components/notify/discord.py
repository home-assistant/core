"""Discord platform for notify component."""
import logging
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['discord.py==0.16.0']

CONF_TOKEN = 'token'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string
})


def get_service(hass, config, discovery_info=None):
    """Get the Discord notification service."""
    return DiscordNotificationService(hass, client_id)


class DiscordNotificationService(BaseNotificationService):
    """Implement the notification service for Discord."""

    def __init__(self, hass, client_id):
        """Initialize the service."""
        self.client_id = client_id
        self.hass = hass
    @asyncio.coroutine
    def async_send_message(self, message, target):
        """Login to Discord and send message."""
        import discord
        discord_bot = discord.Client(loop=self.hass.loop)

        """Logs in."""
        yield from discord_bot.login(self.client_id)

        """Gets channel ID(s) and sends message."""
        for channelid in target:
            channel = discord.Object(id=channelid)
            yield from discord_bot.send_message(channel, message)

        """Closes connection and logs out."""
        yield from discord_bot.logout()
        yield from discord_bot.close()

    def send_message(self, message=None, target=None, **kwargs):
        """Send a message using Discord."""
        self.hass.async_add_job(self.async_send_message(message, target))

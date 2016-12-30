"""
Discord platform for notify component.
"""
import logging
import asyncio

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (
    ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['aiohttp==1.1.6','websockets','discord.py==0.16.0']

CONF_CLIENT_ID = 'client_id'
#CONF_CHANNEL_ID = 'channel_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    #vol.Required(CONF_CHANNEL_ID): cv.string,
})


def get_service(hass, config):
    """Get the Discord notification service."""


    try:
        client_id=config.get(CONF_CLIENT_ID)
        #channel_id=config.get(CONF_CHANNEL_ID)
    except RandomError:
        _LOGGER.error(
            "Please specify a client ID")
        return None
    return DiscordNotificationService(hass,client_id)

class DiscordNotificationService(BaseNotificationService):
    """Implement the notification service for Discord"""

    def __init__(self,hass,client_id):
        """Initialize the service."""
        import discord
        self.client_id = client_id
        self.hass = hass
        #self.discord_bot = discord.Client(loop=self.hass.loop)

    async def async_send_message(self,message,target):
        import discord
        discord_bot = discord.Client(loop=self.hass.loop)
        """Logs in"""
        await discord_bot.login(self.client_id)

        """Gets channel ID(s) and sends message"""
        for channelid in target:
          channel = discord.Object(id=channelid)
          await discord_bot.send_message(channel, message)
        
        """Closes connection and logs out"""
        #print("logging out")
        await discord_bot.logout()
        #print("closing connection")
        await discord_bot.close()

    def send_message(self, message=None,target=None, **kwargs):
        """Send a message using Discord"""
        asyncio.gather(self.async_send_message(message,target),loop=self.hass.loop)

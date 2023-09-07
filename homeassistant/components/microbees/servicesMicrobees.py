
from homeassistant.helpers import aiohttp_client
import logging
import json
from .const import SENDCOMMAND_URL,GETMYBEES_URL
_LOGGER = logging.getLogger(__name__)


async def sendCommand(self, data):
    _LOGGER.info("sendCommand: %s" % data)
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % self.token,
    }
    async with aiohttp_client.async_create_clientsession(self.hass) as session:
        async with session.post(
            SENDCOMMAND_URL,
            json=data,
            headers=headers
        ) as resp:
            await resp.text()


async def getBees(hass,token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % token,
    }
    async with aiohttp_client.async_create_clientsession(hass) as session:
        async with session.post(
            GETMYBEES_URL, headers=headers
        ) as resp:
            data = await resp.text()
            js = json.loads(data)
            return js.get("data")

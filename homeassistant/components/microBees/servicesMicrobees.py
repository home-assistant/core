import aiohttp
import logging
import json

_LOGGER = logging.getLogger(__name__)


async def sendCommand(token, data):
    _LOGGER.info("sendCommand: %s" % data)
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % token,
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(
            "https://dev.microbees.com/v/1_0/sendCommand",
            json=data,
        ) as resp:
            await resp.text()


async def getBees(token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % token,
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(
            "https://dev.microbees.com/v/1_0/getMyBees", headers=headers
        ) as resp:
            data = await resp.text()
            js = json.loads(data)
            return js.get("data")
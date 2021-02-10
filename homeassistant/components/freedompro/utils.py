"""Support for Freedompro utils."""
import asyncio
import logging

import aiohttp
from aiohttp.hdrs import AUTHORIZATION
import async_timeout

from homeassistant.const import HTTP_OK, HTTP_UNAUTHORIZED
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import FREEDOMPRO_URL

_LOGGER = logging.getLogger(__name__)


async def get_list(hass, apikey):
    """Return list of accessories."""
    headers = {
        AUTHORIZATION: f"Bearer {apikey}",
        "Content-Type": "application/json",
    }
    try:
        httpsession = async_get_clientsession(hass)
        with async_timeout.timeout(10000):
            resp = await httpsession.get(FREEDOMPRO_URL, headers=headers)

    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.exception("Error on %s", FREEDOMPRO_URL)
        return {"state": False, "code": -200}

    status = resp.status
    if status == HTTP_OK:
        devices = await resp.json()
        return {"state": True, "devices": devices}
    if status == HTTP_UNAUTHORIZED:
        _LOGGER.error("Unauthorized (bad token?) on %s", FREEDOMPRO_URL)
        return {"state": False, "code": -201}

    _LOGGER.error("HTTP error %d on %s", resp.status, FREEDOMPRO_URL)
    return {"state": False, "code": -200}


async def get_states(hass, apikey):
    """Return state of accessories."""
    headers = {
        AUTHORIZATION: f"Bearer {apikey}",
        "Content-Type": "application/json",
    }
    try:
        httpsession = async_get_clientsession(hass)
        with async_timeout.timeout(10000):
            resp = await httpsession.get(f"{FREEDOMPRO_URL}/state", headers=headers)
            status = resp.status
            if status == HTTP_OK:
                data = await resp.json()
                return data
            return []
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.exception("Error on %s", FREEDOMPRO_URL)
        return []


async def put_state(hass, apikey, uid, payload):
    """Set state of accessory."""
    headers = {
        AUTHORIZATION: f"Bearer {apikey}",
        "Content-Type": "application/json",
    }
    try:
        httpsession = async_get_clientsession(hass)
        with async_timeout.timeout(10000):
            resp = await httpsession.put(
                f"{FREEDOMPRO_URL}/{uid}/state", data=payload, headers=headers
            )
            status = resp.status
            if status == HTTP_OK:
                data = await resp.json()
                if "state" in data:
                    return data["state"]
            return {}
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.exception("Error on %s", FREEDOMPRO_URL)
        return {}

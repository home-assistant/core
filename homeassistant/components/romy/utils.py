"""Helper functions for the ROMY integration."""
import asyncio
import logging

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


async def async_query(
    hass: HomeAssistant, host: str, port: int, command: str, timeout: int = 3
) -> tuple[bool, str]:
    """Call function to Send a http query."""
    ret, resp, _ = await _async_query(hass, host, port, command, timeout)
    return ret, resp


async def async_query_with_http_status(
    hass: HomeAssistant, host: str, port: int, command: str, timeout: int = 3
) -> tuple[bool, str, int]:
    """Call function to Send a http query which returns http status code additionally."""
    ret, resp, http_status = await _async_query(hass, host, port, command, timeout)
    return ret, resp, http_status


async def _async_query(
    hass: HomeAssistant,
    host: str,
    port: int,
    command: str,
    timeout: int,
) -> tuple[bool, str, int]:
    """Send a http query."""
    _LOGGER.debug("async_query host=%s, port=%s, command=%s", host, port, command)
    try:
        websession = async_get_clientsession(hass)

        with async_timeout.timeout(timeout):
            url = f"http://{host}:{port}/{command}"
            _LOGGER.debug("requesting url: %s", url)
            webresponse = await websession.get(url)
            _LOGGER.debug("http returned: %s", webresponse.status)

            # if we don't get http ok response return error
            ret = True
            if webresponse.status != 200:
                ret = False
            response = await webresponse.read()
            response_decoded = response.decode("utf-8")
            _LOGGER.debug("web response: %s", response_decoded)

            return ret, response_decoded, webresponse.status

    except asyncio.TimeoutError:
        _LOGGER.warning("ROMY robot timed out")
        return False, "timeout", 0
    except aiohttp.ClientError as error:
        _LOGGER.warning("Error getting ROMY robot data: %s", error)
        return False, str(error), 0

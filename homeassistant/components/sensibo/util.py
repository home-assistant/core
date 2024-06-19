"""Utils for Sensibo integration."""

from __future__ import annotations

import asyncio

from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER, SENSIBO_ERRORS, TIMEOUT


async def async_validate_api(hass: HomeAssistant, api_key: str) -> str:
    """Validate the api and return username."""
    client = SensiboClient(
        api_key,
        session=async_get_clientsession(hass),
        timeout=TIMEOUT,
    )

    try:
        async with asyncio.timeout(TIMEOUT):
            device_query = await client.async_get_devices()
            user_query = await client.async_get_me()
    except AuthenticationError as err:
        LOGGER.error("Could not authenticate on Sensibo servers %s", err)
        raise AuthenticationError from err
    except SENSIBO_ERRORS as err:
        LOGGER.error("Failed to get information from Sensibo servers %s", err)
        raise ConnectionError from err

    devices = device_query["result"]
    user: str = user_query["result"].get("username")
    if not devices:
        LOGGER.error("Could not retrieve any devices from Sensibo servers")
        raise NoDevicesError
    if not user:
        LOGGER.error("Could not retrieve username from Sensibo servers")
        raise NoUsernameError
    return user


class NoDevicesError(Exception):
    """No devices from Sensibo api."""


class NoUsernameError(Exception):
    """No username from Sensibo api."""

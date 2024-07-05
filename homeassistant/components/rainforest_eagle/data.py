"""Rainforest data."""

from __future__ import annotations

import asyncio
import logging

import aioeagle
import aiohttp
from eagle100 import Eagle as Eagle100Reader
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import TYPE_EAGLE_100, TYPE_EAGLE_200

_LOGGER = logging.getLogger(__name__)

UPDATE_100_ERRORS = (ConnectError, HTTPError, Timeout)


class RainforestError(HomeAssistantError):
    """Base error."""


class CannotConnect(RainforestError):
    """Error to indicate a request failed."""


class InvalidAuth(RainforestError):
    """Error to indicate bad auth."""


async def async_get_type(hass, cloud_id, install_code, host):
    """Try API call 'get_network_info' to see if target device is Eagle-100 or Eagle-200."""
    # For EAGLE-200, fetch the hardware address of the meter too.
    hub = aioeagle.EagleHub(
        aiohttp_client.async_get_clientsession(hass), cloud_id, install_code, host=host
    )

    try:
        async with asyncio.timeout(30):
            meters = await hub.get_device_list()
    except aioeagle.BadAuth as err:
        raise InvalidAuth from err
    except (KeyError, aiohttp.ClientError):
        # This can happen if it's an eagle-100
        meters = None

    if meters is not None:
        if meters:
            hardware_address = meters[0].hardware_address
        else:
            hardware_address = None

        return TYPE_EAGLE_200, hardware_address

    reader = Eagle100Reader(cloud_id, install_code, host)

    try:
        response = await hass.async_add_executor_job(reader.get_network_info)
    except ValueError as err:
        # This could be invalid auth because it doesn't check 401 and tries to read JSON.
        raise InvalidAuth from err
    except UPDATE_100_ERRORS as error:
        _LOGGER.error("Failed to connect during setup: %s", error)
        raise CannotConnect from error

    # Branch to test if target is Legacy Model
    if (
        "NetworkInfo" in response
        and response["NetworkInfo"].get("ModelId") == "Z109-EAGLE"
    ):
        return TYPE_EAGLE_100, None

    return None, None

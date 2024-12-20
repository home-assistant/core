"""Helper functions for the Microsoft Speech integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import VOICES_ENDPOINT

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect using REST API."""

    _LOGGER.debug("Validating Microsoft Speech configuration via REST API")
    api_key = data[CONF_API_KEY]
    region = data[CONF_REGION]
    voices_endpoint = VOICES_ENDPOINT.format(region=region)

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
    }

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(voices_endpoint, headers=headers) as response,
        ):
            if response.status == 200:
                _LOGGER.debug("Successfully validated Microsoft Speech configuration")
            elif response.status == 400:
                _LOGGER.error("Bad request: %s", response.reason)
                raise InvalidAuth("Bad request: Invalid API key or region")
            elif response.status == 401:
                _LOGGER.error("Unauthorized: %s", response.reason)
                raise InvalidAuth("Unauthorized: Invalid API key or region")
            elif response.status == 429:
                _LOGGER.error("Too many requests: %s", response.reason)
                raise TooManyRequests("Too many requests: Rate limit exceeded")
            elif response.status == 502:
                _LOGGER.error("Bad gateway: %s", response.reason)
                raise CannotConnect("Bad gateway: Network or server-side issue")
            else:
                _LOGGER.error(
                    "Failed to connect to Microsoft Speech API: %s",
                    response.reason,
                )
                raise CannotConnect(
                    f"HTTP Error: {response.status} - {response.reason}"
                )

    except aiohttp.ClientError as ex:
        _LOGGER.error(
            "Connection error while validating Microsoft Speech configuration: %s", ex
        )
        raise CannotConnect("Unable to connect to Microsoft Speech API") from ex

    return {"title": data[CONF_NAME]}


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class TooManyRequests(HomeAssistantError):
    """Error to indicate too many requests have been made."""

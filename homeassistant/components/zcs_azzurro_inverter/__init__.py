"""The zcs_azzurro integration."""
from __future__ import annotations

import logging
from typing import Any

import requests
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    AUTH_KEY,
    AUTH_VALUE,
    CLIENT_AUTH_KEY,
    COMMAND_KEY,
    CONTENT_TYPE,
    DEVICES_ALARMS_COMMAND,
    DEVICES_ALARMS_KEY,
    DOMAIN,
    ENDPOINT,
    PARAMS_KEY,
    PARAMS_REQUIRED_VALUES_KEY,
    PARAMS_THING_KEY,
    REALTIME_DATA_COMMAND,
    REALTIME_DATA_KEY,
    REQUEST_TIMEOUT,
    REQUIRED_VALUES_ALL,
    REQUIRED_VALUES_SEP,
    RESPONSE_SUCCESS_KEY,
    RESPONSE_VALUES_KEY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up zcs_azzurro from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def post_request(client: str, data: dict) -> requests.Response:
    """client: the client to set in header.

    data: the dictionary to be sent as json
    return: the response from request.
    """
    headers = {
        AUTH_KEY: AUTH_VALUE,
        CLIENT_AUTH_KEY: client,
        "Content-Type": CONTENT_TYPE,
    }

    _LOGGER.debug(
        "post_request called with client %s, data %s. headers are %s",
        client,
        data,
        headers,
    )
    try:
        response = requests.post(
            ENDPOINT, headers=headers, json=data, timeout=REQUEST_TIMEOUT
        )
        if response.status_code == 401:
            raise InvalidAuth
        return response
    except RequestConnectionError as exc:
        raise CannotConnect from exc


async def realtime_data_request(
    hass: HomeAssistant,
    client: str,
    thing: str,
    required_values: list[str] | None = None,
) -> dict:
    """Request realtime data."""
    if not required_values:
        required_values = [REQUIRED_VALUES_ALL]
    data = {
        REALTIME_DATA_KEY: {
            COMMAND_KEY: REALTIME_DATA_COMMAND,
            PARAMS_KEY: {
                PARAMS_THING_KEY: thing,
                PARAMS_REQUIRED_VALUES_KEY: REQUIRED_VALUES_SEP.join(required_values),
            },
        }
    }
    response = await hass.async_add_executor_job(post_request, client, data)
    if not response.ok:
        raise ResponseError("Response did not return correctly")
    response_data: dict[str, Any] = response.json()[REALTIME_DATA_KEY]
    _LOGGER.debug("fetched realtime data %s", response_data)
    if not response_data[RESPONSE_SUCCESS_KEY]:
        raise ResponseError("Response did not return correctly")
    return response_data[PARAMS_KEY][RESPONSE_VALUES_KEY][0][thing]


async def alarms_request(hass: HomeAssistant, client: str, thing: str) -> dict:
    """Request alarms."""
    required_values = [REQUIRED_VALUES_ALL]
    data = {
        DEVICES_ALARMS_KEY: {
            COMMAND_KEY: DEVICES_ALARMS_COMMAND,
            PARAMS_KEY: {
                PARAMS_THING_KEY: thing,
                PARAMS_REQUIRED_VALUES_KEY: REQUIRED_VALUES_SEP.join(required_values),
            },
        }
    }
    response = await hass.async_add_executor_job(post_request, client, data)
    if not response.ok:
        raise ResponseError("Response did not return correctly")
    response_data: dict[str, Any] = response.json()[DEVICES_ALARMS_KEY]
    _LOGGER.debug("fetched realtime data %s", response_data)
    if not response_data[RESPONSE_SUCCESS_KEY]:
        raise ResponseError("Response did not return correctly")
    return response_data[PARAMS_KEY][RESPONSE_VALUES_KEY][0][thing]


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ResponseError(HomeAssistantError):
    """Error to indicate there was a not ok response."""

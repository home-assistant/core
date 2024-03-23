"""Config flow for Solis logger integration."""
from __future__ import annotations

from http import HTTPStatus
import logging
import socket
from typing import Any

import aiohttp
from geniushubclient import GeniusHub
import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import GeniusBroker
from .const import (
    DEFAULT_GENIISHUB_MAC,
    DEFAULT_GENIISHUB_TOKEN,
    DEFAULT_GENIUSHUB_HOST,
    DEFAULT_GENIUSHUB_PASSWORD,
    DEFAULT_GENIUSHUB_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MAC_ADDRESS_REGEXP = r"^([0-9A-F]{2}:){5}([0-9A-F]{2})$"

OPTION_1_OR_2_SCHEMA = vol.Schema(
    {
        vol.Optional("option_1_or_2"): cv.boolean,
    }
)

V1_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_MAC): vol.Match(MAC_ADDRESS_REGEXP),
    }
)
V3_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MAC): vol.Match(MAC_ADDRESS_REGEXP),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(V3_API_SCHEMA, V1_API_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


def step_user_data_schema() -> Schema:
    """User data schema."""
    STEP_USER_DATA_SCHEMA = vol.Schema(
        {vol.Optional("option_1_or_2", default=True): bool}, extra=vol.PREVENT_EXTRA
    )
    return STEP_USER_DATA_SCHEMA


def step_user_data_schema_v1() -> Schema:
    """Validate the user input allows us to connect."""
    data = {
        CONF_HOST: DEFAULT_GENIUSHUB_HOST,
        CONF_PASSWORD: DEFAULT_GENIUSHUB_PASSWORD,
        CONF_USERNAME: DEFAULT_GENIUSHUB_USERNAME,
    }

    STEP_USER_DATA_SCHEMA_V1 = vol.Schema(
        {
            vol.Required(CONF_HOST, default=data.get(CONF_HOST)): str,
            vol.Required(CONF_USERNAME, default=data.get(CONF_USERNAME)): str,
            vol.Required(CONF_PASSWORD, default=data.get(CONF_PASSWORD)): str,
        },
        extra=vol.PREVENT_EXTRA,
    )
    _LOGGER.debug(
        "config_flow.py:step_user_data_schema_v1: STEP_USER_DATA_SCHEMA_v1: ",
        extra=STEP_USER_DATA_SCHEMA_V1,
    )
    return STEP_USER_DATA_SCHEMA_V1


def step_user_data_schema_v3() -> Schema:
    """User data schema for version 3 API."""
    data = {
        CONF_MAC: DEFAULT_GENIISHUB_MAC,
        CONF_TOKEN: DEFAULT_GENIISHUB_TOKEN,
    }
    STEP_USER_DATA_SCHEMA_V3 = vol.Schema(
        {
            vol.Required(CONF_TOKEN, default=data.get(CONF_TOKEN)): str,
            vol.Optional(CONF_MAC, default=data.get(CONF_MAC)): str,
        },
        extra=vol.PREVENT_EXTRA,
    )
    _LOGGER.debug(
        "config_flow.py:step_user_data_schema_v3: STEP_USER_DATA_SCHEMA_v3: ",
        extra=STEP_USER_DATA_SCHEMA_V3,
    )
    return STEP_USER_DATA_SCHEMA_V3


async def validate_input(
    hass: HomeAssistant, hass_data_in: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hass_data = dict(hass_data_in)
    if CONF_HOST in hass_data:
        args = (hass_data.pop(CONF_HOST),)
    else:
        args = (hass_data.pop(CONF_TOKEN),)

    hub_uid = hass_data.pop(CONF_MAC, None)

    client = GeniusHub(*args, **hass_data, session=async_get_clientsession(hass))

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["broker"] = GeniusBroker(hass, client, hub_uid)

    await client.update()

    _LOGGER.debug("config_flow.py:validate_input: ", extra=hass_data)

    return {"title": args}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solis logger."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User config step for determine v1 or v3."""
        _LOGGER.debug("config_flow.py:ConfigFlow.async_step_user")
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=step_user_data_schema()
            )

        if user_input.get("option_1_or_2", False):
            return await self.async_step_user_v1()
        return await self.async_step_user_v3()

    async def async_step_user_v1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 1 configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="user_v1", data_schema=step_user_data_schema_v1()
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)

        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "unauthorized"
            else:
                errors["base"] = "invalid_host"

        except socket.gaierror:
            errors["base"] = "invalid_host"

        except TimeoutError:
            errors["base"] = "cannot_connect"

        except aiohttp.ClientConnectionError:
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "config_flow.py:ConfigFlow.async_step_user: validation passed:",
                extra=user_input,
            )
            # await self.async_set_unique_id(user_input.device_id) # not sure this is permitted as the user can change the device_id
            # self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "config_flow.py:ConfigFlow.async_step_user: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            data_schema=step_user_data_schema(),
            errors=errors,
        )

    async def async_step_user_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 3 configuration."""
        _LOGGER.debug(
            "config_flow.py:ConfigFlow.async_step_user_v3: ", extra=user_input
        )
        if user_input is None:
            return self.async_show_form(
                step_id="user_v3", data_schema=step_user_data_schema_v3()
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)

        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "unauthorized_token"
            else:
                errors["base"] = "invalid_host"

        except socket.gaierror:
            errors["base"] = "invalid_host"

        except TimeoutError:
            errors["base"] = "cannot_connect"

        except aiohttp.ClientConnectionError:
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "config_flow.py:ConfigFlow.async_step_user: validation passed: ",
                extra=user_input,
            )
            # await self.async_set_unique_id(user_input.device_id) # not sure this is permitted as the user can change the device_id
            # self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug(
            "config_flow.py:ConfigFlow.async_step_user: validation failed: ",
            extra=user_input,
        )

        return self.async_show_form(
            step_id="user",
            data_schema=step_user_data_schema(),
            errors=errors,
        )

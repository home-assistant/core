"""Adds config flow for Sensibo integration."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import async_timeout
from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError, SensiboError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME, DOMAIN, TIMEOUT

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


async def async_validate_api(hass: HomeAssistant, api_key: str) -> bool:
    """Get data from API."""
    client = SensiboClient(
        api_key,
        session=async_get_clientsession(hass),
        timeout=TIMEOUT,
    )

    try:
        async with async_timeout.timeout(TIMEOUT):
            if await client.async_get_devices():
                return True
    except (
        aiohttp.ClientConnectionError,
        asyncio.TimeoutError,
        AuthenticationError,
        SensiboError,
    ) as err:
        _LOGGER.error("Failed to get devices from Sensibo servers %s", err)
    return False


async def async_get_username(hass: HomeAssistant, api_key: str) -> str | None:
    """Return username from API."""
    client = SensiboClient(
        api_key,
        session=async_get_clientsession(hass),
        timeout=TIMEOUT,
    )

    try:
        async with async_timeout.timeout(TIMEOUT):
            userdetails = await client.async_get_me()
    except (
        aiohttp.ClientConnectionError,
        asyncio.TimeoutError,
        AuthenticationError,
        SensiboError,
    ) as err:
        _LOGGER.error("Failed to get user details from Sensibo servers %s", err)
        return None

    if userdetails:
        return userdetails["result"].get("username")
    return None


class SensiboConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensibo integration."""

    VERSION = 2

    async def async_step_import(self, config: dict) -> FlowResult:
        """Import a configuration from config.yaml."""

        self.context.update(
            {"title_placeholders": {"Sensibo": f"YAML import {DOMAIN}"}}
        )
        return await self.async_step_user(user_input=config)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input:

            api_key = user_input[CONF_API_KEY]

            validate = await async_validate_api(self.hass, api_key)
            if validate:
                username = await async_get_username(self.hass, api_key)
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_API_KEY: api_key},
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

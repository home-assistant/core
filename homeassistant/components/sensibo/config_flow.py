"""Adds config flow for Sensibo integration."""
from __future__ import annotations

import async_timeout
from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME, DOMAIN, LOGGER, SENSIBO_ERRORS, TIMEOUT

INVALID_AUTH = "invalid_auth"
CANNOT_CONNECT = "cannot_connect"
NO_DEVICES = "no_devices"
NO_USERNAME = "no_username"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


async def async_validate_api(hass: HomeAssistant, api_key: str) -> str:
    """Get data from API."""
    client = SensiboClient(
        api_key,
        session=async_get_clientsession(hass),
        timeout=TIMEOUT,
    )

    try:
        async with async_timeout.timeout(TIMEOUT):
            device_query = await client.async_get_devices()
            user_query = await client.async_get_me()
    except AuthenticationError as err:
        LOGGER.error("Could not authenticate on Sensibo servers %s", err)
        return INVALID_AUTH
    except SENSIBO_ERRORS as err:
        LOGGER.error("Failed to get information from Sensibo servers %s", err)
        return CANNOT_CONNECT

    devices = device_query["result"]
    user = user_query["result"].get("username")
    if not devices:
        return NO_DEVICES
    if not user:
        return NO_USERNAME
    return user


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
            if validate not in [INVALID_AUTH, CANNOT_CONNECT, NO_DEVICES, NO_USERNAME]:
                await self.async_set_unique_id(validate)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_API_KEY: api_key},
                )
            errors["base"] = validate

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

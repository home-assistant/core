"""Adds config flow for Sensibo integration."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import async_timeout
from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError, SensiboError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME, DOMAIN, LOGGER, TIMEOUT

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
            await client.async_get_devices()
    except AuthenticationError as err:
        LOGGER.error("Failed to authenticate to Sensibo servers %s", err)
        return "invalid_auth"
    except (
        aiohttp.ClientConnectionError,
        asyncio.TimeoutError,
        SensiboError,
    ) as err:
        LOGGER.error("Failed to get devices from Sensibo servers %s", err)
        return "cannot_connect"
    return "validated"


class SensiboConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensibo integration."""

    VERSION = 1

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a configuration from config.yaml."""

        return await self.async_step_user(user_input=config)

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication with Sensibo."""
        errors: dict[str, str] = {}

        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            validate = await async_validate_api(self.hass, api_key)
            if validate != "validated":
                errors["base"] = validate
            else:
                existing_entry = await self.async_set_unique_id(
                    self.context["unique_id"]
                )
                if existing_entry and entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data={
                            **entry.data,
                            CONF_API_KEY: api_key,
                        },
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input:

            api_key = user_input[CONF_API_KEY]

            await self.async_set_unique_id(api_key)
            self._abort_if_unique_id_configured()

            validate = await async_validate_api(self.hass, api_key)
            if validate == "validated":
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

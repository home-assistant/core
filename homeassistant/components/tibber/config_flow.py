"""Adds config flow for Tibber integration."""
from __future__ import annotations

from typing import Any

import aiohttp
import tibber
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
ERR_TIMEOUT = "timeout"
ERR_CLIENT = "cannot_connect"
ERR_TOKEN = "invalid_access_token"
TOKEN_URL = "https://developer.tibber.com/settings/access-token"


class TibberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tibber integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        self._async_abort_entries_match()

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN].replace(" ", "")

            tibber_connection = tibber.Tibber(
                access_token=access_token,
                websession=async_get_clientsession(self.hass),
            )

            errors = {}

            try:
                await tibber_connection.update_info()
            except TimeoutError:
                errors[CONF_ACCESS_TOKEN] = ERR_TIMEOUT
            except tibber.InvalidLogin:
                errors[CONF_ACCESS_TOKEN] = ERR_TOKEN
            except (
                aiohttp.ClientError,
                tibber.RetryableHttpException,
                tibber.FatalHttpException,
            ):
                errors[CONF_ACCESS_TOKEN] = ERR_CLIENT

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    description_placeholders={"url": TOKEN_URL},
                    errors=errors,
                )

            unique_id = tibber_connection.user_id
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=tibber_connection.name,
                data={CONF_ACCESS_TOKEN: access_token},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            description_placeholders={"url": TOKEN_URL},
            errors={},
        )

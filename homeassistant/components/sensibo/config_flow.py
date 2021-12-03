"""Adds config flow for Sensibo integration."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import async_timeout
from pysensibo import SensiboClient, SensiboError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import _INITIAL_FETCH_FIELDS, ALL, DEFAULT_NAME, DOMAIN, TIMEOUT

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


class SensiboConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensibo integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry

    name: str
    api_key: str
    id: list
    errors: dict[str, str] = {}

    async def async_get_data(self) -> list:
        """Get data from API."""
        client = SensiboClient(
            self.api_key,
            session=async_get_clientsession(self.hass),
            timeout=TIMEOUT,
        )

        id_list: list = []
        id_list.append("all")

        try:
            async with async_timeout.timeout(TIMEOUT):
                for dev in await client.async_get_devices(_INITIAL_FETCH_FIELDS):
                    id_list.append(dev["id"])
            return id_list
        except (
            aiohttp.ClientConnectionError,
            asyncio.TimeoutError,
            SensiboError,
        ) as err:
            _LOGGER.error("Failed to get devices from Sensibo servers %s", err)
            self.errors["base"] = "cannot_connect"
        return []

    async def async_step_import(self, config: dict):
        """Import a configuration from config.yaml."""

        self.context.update(
            {"title_placeholders": {"Sensibo": f"YAML import {DOMAIN}"}}
        )
        if CONF_ID not in config:
            config[CONF_ID] = ALL
        if CONF_NAME not in config:
            config[CONF_NAME] = DEFAULT_NAME
        return await self.async_step_user(user_input=config)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        if user_input is not None:

            self.id = []
            if CONF_ID in user_input:
                self.id = user_input[CONF_ID]
            self.api_key = user_input[CONF_API_KEY]
            self.name = user_input[CONF_NAME]

            await self.async_set_unique_id(self.api_key)
            self._abort_if_unique_id_configured()

            validate = await self.async_get_data()
            if validate is not None:
                return await self.async_step_id()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=self.errors,
        )

    async def async_step_id(self, user_input=None):
        """Handle choosing id's."""

        if user_input is not None:
            self.id = user_input[CONF_ID]

        if self.id:
            return self.async_create_entry(
                title=self.name,
                data={
                    CONF_NAME: self.name,
                    CONF_API_KEY: self.api_key,
                    CONF_ID: self.id,
                },
            )

        id_list: list = []
        id_list = await self.async_get_data()

        id_schema = vol.Schema(
            {
                vol.Required(CONF_ID, default=ALL): cv.multi_select(id_list),
            }
        )

        return self.async_show_form(
            step_id="id",
            data_schema=id_schema,
            errors=self.errors,
        )

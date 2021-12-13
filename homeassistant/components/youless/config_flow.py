"""Config flow for youless integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.error import HTTPError, URLError

import voluptuous as vol
from youless_api import YoulessAPI

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class YoulessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for youless."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                api = YoulessAPI(user_input[CONF_HOST])
                await self.hass.async_add_executor_job(api.initialize)
            except (HTTPError, URLError):
                _LOGGER.exception("Cannot connect to host")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_DEVICE: api.mac_address,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

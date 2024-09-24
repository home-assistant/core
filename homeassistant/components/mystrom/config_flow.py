"""Config flow for myStrom integration."""

from __future__ import annotations

import logging
from typing import Any

import pymystrom
from pymystrom.exceptions import MyStromConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "myStrom Device"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
    }
)


class MyStromConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for myStrom."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await pymystrom.get_device_info(user_input[CONF_HOST])
            except MyStromConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured()
                data = {CONF_HOST: user_input[CONF_HOST]}
                title = user_input.get(CONF_NAME) or DEFAULT_NAME
                return self.async_create_entry(title=title, data=data)

        schema = self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

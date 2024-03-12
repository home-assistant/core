"""Config flow for Arve integration."""

from __future__ import annotations

import logging
from typing import Any

from asyncarve import Arve, ArveConnectionError, ArveSensPro
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ArveConfigFlowHadler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Arve."""

    VERSION = 1

    async def _show_setup_form(self, errors: dict[str, str] | None = None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_NAME): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is None:
            return await self._show_setup_form(user_input)

        self._async_abort_entries_match(
            {
                CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                CONF_NAME: user_input[CONF_NAME],
            }
        )

        errors = {}

        access_token = user_input[CONF_ACCESS_TOKEN]
        customer_token = user_input[CONF_CLIENT_SECRET]
        name = user_input[CONF_NAME]

        arve = Arve(
            access_token,
            customer_token,
            name,
        )

        try:
            info: ArveSensPro = await arve.get_sensor_info()
        except ArveConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title=info.name,
            data={
                CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                CONF_NAME: user_input[CONF_NAME],
            },
        )

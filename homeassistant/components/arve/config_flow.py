"""Config flow for Arve integration."""

from __future__ import annotations

import logging
from typing import Any

from asyncarve import Arve, ArveConnectionError, ArveSensPro
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ArveConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Arve."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            arve = Arve(
                user_input[CONF_ACCESS_TOKEN],
                user_input[CONF_CLIENT_SECRET],
                user_input[CONF_NAME],
            )
            try:
                info: ArveSensPro = await arve.get_sensor_info()
            except ArveConnectionError:
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(
                    title=info.name,
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

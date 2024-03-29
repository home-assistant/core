"""Config flow for Rainforest Eagle integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TYPE

from . import data
from .const import CONF_CLOUD_ID, CONF_HARDWARE_ADDRESS, CONF_INSTALL_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


def create_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Create user schema with passed in defaults if available."""
    if user_input is None:
        user_input = {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
            vol.Required(CONF_CLOUD_ID, default=user_input.get(CONF_CLOUD_ID)): str,
            vol.Required(
                CONF_INSTALL_CODE, default=user_input.get(CONF_INSTALL_CODE)
            ): str,
        }
    )


class RainforestEagleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rainforest Eagle."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=create_schema(user_input)
            )

        await self.async_set_unique_id(user_input[CONF_CLOUD_ID])
        errors = {}

        try:
            eagle_type, hardware_address = await data.async_get_type(
                self.hass,
                user_input[CONF_CLOUD_ID],
                user_input[CONF_INSTALL_CODE],
                user_input[CONF_HOST],
            )
        except data.CannotConnect:
            errors["base"] = "cannot_connect"
        except data.InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            user_input[CONF_TYPE] = eagle_type
            user_input[CONF_HARDWARE_ADDRESS] = hardware_address
            return self.async_create_entry(
                title=user_input[CONF_CLOUD_ID], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=create_schema(user_input), errors=errors
        )

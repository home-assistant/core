"""Config flow for Rainforest Eagle integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TYPE

from .const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_100,
    TYPE_EAGLE_200,
)
from .data import CannotConnect, InvalidAuth, async_get_type

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
            eagle_type, hardware_address = await async_get_type(
                self.hass,
                user_input[CONF_CLOUD_ID],
                user_input[CONF_INSTALL_CODE],
                user_input[CONF_HOST],
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Verify it is a known device, first
            if not eagle_type:
                errors["base"] = "unknown_device_type"
            elif eagle_type == TYPE_EAGLE_100:
                user_input[CONF_TYPE] = eagle_type

                # For EAGLE-100, there is no hardware address to select, so set it to None and move on
                user_input[CONF_HARDWARE_ADDRESS] = None
            elif eagle_type == TYPE_EAGLE_200:
                user_input[CONF_TYPE] = eagle_type

                # For EAGLE-200, a connected meter's hardware address is required to create the entry
                if not hardware_address:
                    # hardware_address will be None if there are no meters at all or if none are currently Connected
                    errors["base"] = "no_meters_connected"
                else:
                    user_input[CONF_HARDWARE_ADDRESS] = hardware_address
            else:
                # This is a device that isn't supported, yet, but was detected by async_get_type
                errors["base"] = "unsupported_device_type"

            # All information gathering is done, so if there are no errors at this point, create the entry
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_CLOUD_ID], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=create_schema(user_input), errors=errors
        )

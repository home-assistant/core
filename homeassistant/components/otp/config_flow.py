"""Config flow for One-Time Password (OTP) integration."""

from __future__ import annotations

import binascii
import logging
from typing import Any

import pyotp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_TOKEN

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


class TOTPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for One-Time Password (OTP)."""

    VERSION = 1
    user_input: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    pyotp.TOTP(user_input[CONF_TOKEN]).now
                )
            except binascii.Error:
                errors["base"] = "invalid_code"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_TOKEN])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        await self.async_set_unique_id(import_info[CONF_TOKEN])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_info.get(CONF_NAME, DEFAULT_NAME),
            data=import_info,
        )

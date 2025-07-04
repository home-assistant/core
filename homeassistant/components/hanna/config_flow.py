"""Config flow for Hanna Instruments integration."""

from __future__ import annotations

import logging
from typing import Any

from hanna_cloud import HannaCloudClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL

from .const import DEFAULT_ENCRYPTION_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HannaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hanna Instruments."""

    VERSION = 1
    data_schema = vol.Schema(
        {
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_CODE, default=DEFAULT_ENCRYPTION_KEY): str,
            vol.Required(CONF_SCAN_INTERVAL, default=5): int,
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors=errors,
            )

        try:
            client = HannaCloudClient()
            await self.hass.async_add_executor_job(
                client.authenticate,
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input[CONF_CODE],
            )
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors=errors,
            )
        return self.async_create_entry(
            title=user_input[CONF_EMAIL],
            data=user_input,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.data_schema,
                errors=errors,
            )

        try:
            client = HannaCloudClient()
            await self.hass.async_add_executor_job(
                client.authenticate,
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input[CONF_CODE],
            )
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.data_schema,
                errors=errors,
            )

        # Update the existing entry
        reconfigure_entry = self._get_reconfigure_entry()
        return self.async_update_reload_and_abort(
            reconfigure_entry,
            data=user_input,
        )

"""Config flow for the STIEBEL ELTRON integration."""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.client import ModbusTcpClient
from pystiebeleltron.pystiebeleltron import StiebelEltronAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class StiebelEltronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for STIEBEL ELTRON."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            client = StiebelEltronAPI(
                ModbusTcpClient(user_input[CONF_HOST], port=user_input[CONF_PORT]), 1
            )
            try:
                success = await self.hass.async_add_executor_job(client.update)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not success:
                    errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(title="Stiebel Eltron", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import."""
        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )
        client = StiebelEltronAPI(
            ModbusTcpClient(user_input[CONF_HOST], port=user_input[CONF_PORT]), 1
        )
        try:
            success = await self.hass.async_add_executor_job(client.update)
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        if not success:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            },
        )

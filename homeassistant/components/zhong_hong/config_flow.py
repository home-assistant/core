"""Config flow for ZhongHong HVAC."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from zhong_hong_hvac.hub import ZhongHongGateway

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_GATEWAY_ADDRESS, DEFAULT_GATEWAY_ADDRESS, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    gw_addr = data[CONF_GATEWAY_ADDRESS]

    hub = ZhongHongGateway(host, port, gw_addr)

    try:
        devices = await hass.async_add_executor_job(hub.discovery_ac)
        if not devices:
            raise ConnectionError("No devices found at this address")
    finally:
        # Stop the temporary hub used for validation
        await hass.async_add_executor_job(hub.stop_listen)


class ZhongHongHvacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZhongHong HVAC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            try:
                await validate_input(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(
                    CONF_GATEWAY_ADDRESS, default=DEFAULT_GATEWAY_ADDRESS
                ): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle import from configuration.yaml."""
        _LOGGER.info("Attempting to import ZhongHong HVAC from YAML: %s", user_input)
        return await self.async_step_user(user_input)

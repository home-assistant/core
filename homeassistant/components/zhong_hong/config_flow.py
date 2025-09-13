"""Config flow for ZhongHong integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from zhong_hong_hvac.hub import ZhongHongGateway

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import CONF_GATEWAY_ADDRESS, DEFAULT_GATEWAY_ADDRESS, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_GATEWAY_ADDRESS, default=DEFAULT_GATEWAY_ADDRESS
        ): cv.positive_int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    gateway_address = data[CONF_GATEWAY_ADDRESS]

    hub = ZhongHongGateway(host, port, gateway_address)

    try:
        devices = await hass.async_add_executor_job(hub.discovery_ac)
        _LOGGER.debug("Found %d devices during validation", len(devices))

        await hass.async_add_executor_job(hub.start_listen)
        await asyncio.sleep(1)  # Give it time to connect
        await hass.async_add_executor_job(hub.stop_listen)

    except Exception as err:
        _LOGGER.error("Cannot connect to ZhongHong gateway: %s", err)
        raise CannotConnect from err

    # Return info that you want to store in the config entry
    return {
        "title": f"ZhongHong Gateway ({host}:{port})",
        "devices_found": len(devices),
    }


class ZhongHongConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZhongHong."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    description_placeholders={
                        "devices_found": str(info["devices_found"])
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "default_port": str(DEFAULT_PORT),
                "default_gateway": str(DEFAULT_GATEWAY_ADDRESS),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "cannot_connect"},
                )
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfigure")
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "unknown"},
                )
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data=user_input, reason="reconfigure_successful"
                )

        suggested_values = {
            CONF_HOST: reconfigure_entry.data[CONF_HOST],
            CONF_PORT: reconfigure_entry.data[CONF_PORT],
            CONF_GATEWAY_ADDRESS: reconfigure_entry.data.get(
                CONF_GATEWAY_ADDRESS, DEFAULT_GATEWAY_ADDRESS
            ),
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
from .sensor import DOMAIN, CONF_SERIAL_PORT
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from typing import Any

import serial.tools.list_ports

CONF_MANUAL_PATH = "Enter Manually"


class EDL21ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EDL21."""

    VERSION = 1

    async def async_step_pick_manual(self, user_input: dict[str, Any]) -> FlowResult:
        return self.async_create_entry(title="EDL21", data=user_input)

    async def async_step_user(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            if user_input[CONF_SERIAL_PORT] == CONF_MANUAL_PATH:
                return self.async_show_form(
                    step_id="pick_manual",
                    data_schema=vol.Schema(
                        {
                            vol.Optional(
                                CONF_NAME, default=user_input[CONF_NAME]
                            ): cv.string,
                            vol.Required(CONF_SERIAL_PORT): cv.string,
                        }
                    ),
                )
            return self.async_create_entry(title="EDL21", data=user_input)

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [f"{p.device}" for p in ports]

        if not list_of_ports:
            return self.async_show_form(
                step_id="pick_manual",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_NAME, default=""): cv.string,
                        vol.Required(CONF_SERIAL_PORT): cv.string,
                    }
                ),
            )

        list_of_ports.append(CONF_MANUAL_PATH)

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=""): cv.string,
                vol.Required(CONF_SERIAL_PORT): vol.In(list_of_ports),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

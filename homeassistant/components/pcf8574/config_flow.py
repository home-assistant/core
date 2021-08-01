"""Config flow for pcf8574 integration."""
from __future__ import annotations

import logging
from typing import Any

from pcf8574 import PCF8574
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("i2c_port_num", default=0): vol.Coerce(int),
        vol.Required(
            "i2c_address", default=0x20, description="0x20 hex is 32 dec"
        ): vol.Coerce(
            int
        ),  # 0x20 = dec 32
        vol.Optional("invert_logic", default=False): cv.boolean,
        vol.Optional("switch_1_name"): cv.string,
        vol.Optional("switch_2_name"): cv.string,
        vol.Optional("switch_3_name"): cv.string,
        vol.Optional("switch_4_name"): cv.string,
        vol.Optional("switch_5_name"): cv.string,
        vol.Optional("switch_6_name"): cv.string,
        vol.Optional("switch_7_name"): cv.string,
        vol.Optional("switch_8_name"): cv.string,
        vol.Optional(CONF_NAME, default="PCF8574 Switch"): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    pcf = PCF8574(data["i2c_port_num"], data["i2c_address"])
    pcf.port[0]

    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pcf8574."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except OSError:
            errors["base"] = "ioerror"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

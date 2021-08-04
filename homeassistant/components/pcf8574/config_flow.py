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

from .const import (
    CONF_I2C_ADDRESS,
    CONF_I2C_BUS_NUM,
    CONF_INPUT,
    CONF_INVERT_LOGIC,
    CONF_PIN_NAME,
    CONF_PINS,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS_NUM,
    DEFAULT_INVERT_LOGIC,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_I2C_BUS_NUM, default=DEFAULT_I2C_BUS_NUM): vol.Coerce(int),
        vol.Required(
            CONF_I2C_ADDRESS,
            default=DEFAULT_I2C_ADDRESS,
            description="0x20 hex is 32 dec",
        ): vol.Coerce(
            int
        ),  # 0x20 = dec 32
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    pcf = PCF8574(data[CONF_I2C_BUS_NUM], data[CONF_I2C_ADDRESS])
    pcf.port[0]

    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pcf8574."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        device_unique_id = (
            f"{user_input[CONF_I2C_BUS_NUM]}_{user_input[CONF_I2C_ADDRESS]}"
        )
        await self.async_set_unique_id(device_unique_id)
        self._abort_if_unique_id_configured()

        try:

            await validate_input(self.hass, user_input)
        except OSError:
            errors["base"] = "ioerror"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.data = user_input
            self.data[CONF_PINS] = []
            return await self.async_step_pin()
            # return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle pin tep."""
        errors: dict[str, Any] = {}
        pin_num = len(self.data[CONF_PINS])
        # first run len=0 -> pin_num = 0
        # second run len=1 -> pin_num = 1
        last_pin = pin_num == 7

        if user_input is None:
            pin_name = f"pin_{pin_num}_name"
            step_pin_data_schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC
                    ): cv.boolean,
                    vol.Optional(CONF_PIN_NAME, default=pin_name): cv.string,
                    vol.Optional(CONF_INPUT, default=False): cv.boolean,
                }
            )
            if not last_pin:
                step_pin_data_schema = step_pin_data_schema.extend(
                    {vol.Optional("add_another", default=False): cv.boolean}
                )
            return self.async_show_form(
                step_id="pin", data_schema=step_pin_data_schema, errors=errors
            )
        else:
            self.data[CONF_PINS].append(
                {
                    "pin_num": pin_num,
                    CONF_PIN_NAME: user_input[CONF_PIN_NAME],
                    CONF_INPUT: user_input[CONF_INPUT],
                    CONF_INVERT_LOGIC: user_input[CONF_INVERT_LOGIC],
                }
            )

            if user_input.get("add_another") and not last_pin:
                return await self.async_step_pin()
            else:
                return self.async_create_entry(
                    title=self.data[CONF_NAME], data=self.data
                )

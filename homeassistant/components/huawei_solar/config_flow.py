"""Config flow for Huawei Solar integration."""
from __future__ import annotations

import logging
from typing import Any

from huawei_solar import AsyncHuaweiSolar, ConnectionException, register_names as rn
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SLAVE_IDS, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 502

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_SLAVE_IDS, default="0"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        inverter = await AsyncHuaweiSolar.create(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            slave=data[CONF_SLAVE_IDS][0],
        )

        model_name, serial_number = await inverter.get_multiple(
            [rn.MODEL_NAME, rn.SERIAL_NUMBER]
        )

        # Return info that you want to store in the config entry.
        return {"model_name": model_name.value, "serial_number": serial_number.value}
    finally:
        # Cleanup this inverter object explicitly to prevent it from trying to maintain a modbus connection
        await inverter.stop()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Huawei Solar."""

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

            user_input[CONF_SLAVE_IDS] = list(
                map(int, user_input[CONF_SLAVE_IDS].split(","))
            )
            info = await validate_input(self.hass, user_input)

            await self.async_set_unique_id(info["serial_number"])
            self._abort_if_unique_id_configured()
        except ConnectionException:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["model_name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

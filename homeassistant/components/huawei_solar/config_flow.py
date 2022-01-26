"""Config flow for Huawei Solar integration."""
from __future__ import annotations

import logging
from typing import Any

from huawei_solar import (
    AsyncHuaweiSolar,
    ConnectionException,
    HuaweiSolarException,
    ReadException,
    register_names as rn,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_SLAVE_IDS, DEFAULT_PORT, DEFAULT_SLAVE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SLAVE_IDS, default=str(DEFAULT_SLAVE_ID)): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    inverter = None
    try:
        inverter = await AsyncHuaweiSolar.create(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            slave=data[CONF_SLAVE_IDS][0],
        )

        model_name, serial_number = await inverter.get_multiple(
            [rn.MODEL_NAME, rn.SERIAL_NUMBER]
        )

        _LOGGER.info(
            "Successfully connected to inverter %s with SN %s",
            model_name.value,
            serial_number.value,
        )

        # Also validate the other slave-ids
        for slave_id in data[CONF_SLAVE_IDS][1:]:
            try:
                slave_model_name, slave_serial_number = await inverter.get_multiple(
                    [rn.MODEL_NAME, rn.SERIAL_NUMBER], slave_id
                )

                _LOGGER.info(
                    "Successfully connected to slave inverter %s: %s with SN %s",
                    slave_id,
                    slave_model_name.value,
                    slave_serial_number.value,
                )
            except HuaweiSolarException as err:
                _LOGGER.error("Could not connect to slave %s", slave_id)
                raise SlaveException(f"Could not connect to slave {slave_id}") from err

        # Return info that you want to store in the config entry.
        return {"model_name": model_name.value, "serial_number": serial_number.value}

    finally:
        if inverter is not None:
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

        except ConnectionException:
            errors["base"] = "cannot_connect"
        except SlaveException:
            errors["base"] = "slave_cannot_connect"
        except ReadException:
            errors["base"] = "read_error"
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["serial_number"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["model_name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class SlaveException(Exception):
    """Error while testing communication with a slave."""

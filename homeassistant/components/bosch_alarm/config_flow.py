"""Config flow for Bosch Alarm integration."""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any

from bosch_alarm_mode2 import Panel
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
)
import homeassistant.helpers.config_validation as cv

from .const import CONF_INSTALLER_CODE, CONF_USER_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=7700): cv.positive_int,
    }
)

STEP_AUTH_DATA_SCHEMA_SOLUTION = vol.Schema(
    {
        vol.Required(CONF_USER_CODE): str,
    }
)

STEP_AUTH_DATA_SCHEMA_AMAX = vol.Schema(
    {
        vol.Required(CONF_INSTALLER_CODE): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_AUTH_DATA_SCHEMA_BG = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_INIT_DATA_SCHEMA = vol.Schema({vol.Optional(CONF_CODE): str})


async def try_connect(
    data: dict[str, Any], load_selector: int = 0
) -> tuple[str, int | None]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    panel = Panel(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        automation_code=data.get(CONF_PASSWORD),
        installer_or_user_code=data.get(CONF_INSTALLER_CODE, data.get(CONF_USER_CODE)),
    )

    try:
        await panel.connect(load_selector)
    finally:
        await panel.disconnect()

    return (panel.model, panel.serial_number)


class BoschAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch Alarm."""

    def __init__(self) -> None:
        """Init config flow."""

        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Use load_selector = 0 to fetch the panel model without authentication.
                (model, serial) = await try_connect(user_input, 0)
            except (
                OSError,
                ConnectionRefusedError,
                ssl.SSLError,
                asyncio.exceptions.TimeoutError,
            ) as e:
                _LOGGER.error("Connection Error: %s", e)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._data = user_input
                self._data[CONF_MODEL] = model
                return await self.async_step_auth()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        errors: dict[str, str] = {}

        # Each model variant requires a different authentication flow
        if "Solution" in self._data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_SOLUTION
        elif "AMAX" in self._data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_AMAX
        else:
            schema = STEP_AUTH_DATA_SCHEMA_BG

        if user_input is not None:
            self._data.update(user_input)
            try:
                (model, serial_number) = await try_connect(
                    self._data, Panel.LOAD_EXTENDED_INFO
                )
            except (PermissionError, ValueError) as e:
                errors["base"] = "invalid_auth"
                _LOGGER.error("Authentication Error: %s", e)
            except (
                OSError,
                ConnectionRefusedError,
                ssl.SSLError,
                TimeoutError,
            ) as e:
                _LOGGER.error("Connection Error: %s", e)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if serial_number:
                    await self.async_set_unique_id(str(serial_number))
                    self._abort_if_unique_id_configured()
                else:
                    self._async_abort_entries_match({CONF_HOST: self._data[CONF_HOST]})
                return self.async_create_entry(title=f"Bosch {model}", data=self._data)

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

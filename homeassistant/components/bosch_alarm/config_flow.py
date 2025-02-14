"""Config flow for Bosch Alarm integration."""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any

from bosch_alarm_mode2 import Panel
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant, callback
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
    hass: HomeAssistant, data: dict[str, Any], load_selector: int = 0
):
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
    except (PermissionError, ValueError) as err:
        _LOGGER.exception("Authentication Error")
        raise RuntimeError("invalid_auth") from err
    except (
        OSError,
        ConnectionRefusedError,
        ssl.SSLError,
        asyncio.exceptions.TimeoutError,
    ) as err:
        _LOGGER.exception("Connection Error")
        raise RuntimeError("cannot_connect") from err
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Unknown Error")
        raise RuntimeError("unknown") from err
    finally:
        await panel.disconnect()

    return (panel.model, panel.serial_number)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch Alarm."""

    VERSION = 4
    entry: config_entries.ConfigEntry | None = None
    data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Provide a handler for the options flow."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        try:
            # Use load_selector = 0 to fetch the panel model without authentication.
            (model, _) = await try_connect(self.hass, user_input, 0)
            self.data = user_input
            self.data[CONF_MODEL] = model
            return await self.async_step_auth()
        except RuntimeError as ex:
            _LOGGER.info(user_input)
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, user_input
                ),
                errors={"base": ex.args[0]},
            )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        if "Solution" in self.data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_SOLUTION
        elif "AMAX" in self.data[CONF_MODEL]:
            schema = STEP_AUTH_DATA_SCHEMA_AMAX
        else:
            schema = STEP_AUTH_DATA_SCHEMA_BG

        if user_input is None:
            return self.async_show_form(step_id="auth", data_schema=schema)
        self.data.update(user_input)
        try:
            (model, serial_number) = await try_connect(
                self.hass, self.data, Panel.LOAD_EXTENDED_INFO
            )
            await self.async_set_unique_id(str(serial_number))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"Bosch {model}", data=self.data)
        except RuntimeError as ex:
            return self.async_show_form(
                step_id="auth",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": ex.args[0]},
            )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Bosch Alarm."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_INIT_DATA_SCHEMA, self.config_entry.options
            ),
        )

"""Config flow for JustNimbus integration."""
from __future__ import annotations

import logging
from typing import Any

import justnimbus
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

scan_interval = vol.Required(CONF_SCAN_INTERVAL, default=5)
scan_interval_options = vol.In(
    (
        1,
        5,
        15,
    ),
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        scan_interval: scan_interval_options,
    },
)


class JustNimbusError(HomeAssistantError):
    """Base exception of the JustNimbus integration."""


class InvalidClientId(JustNimbusError):
    """Exception to be raised by JustNimbus when the client id provided is invalid."""


class CannotConnect(JustNimbusError):
    """Error to indicate we cannot connect."""


class JustNimbus:
    """Wrapper to be used by config flow to check for a valid client id."""

    def __init__(self, client_id: str) -> None:
        """Initialize."""
        self.client_id = client_id

    def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        justnimbus.JustNimbusClient(client_id=self.client_id).get_data()
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    justnimbus_wrapper = JustNimbus(data[CONF_CLIENT_ID])

    try:
        if not await hass.async_add_executor_job(justnimbus_wrapper.authenticate):
            raise CannotConnect
    except justnimbus.InvalidClientID as error:
        raise InvalidClientId from error
    except justnimbus.JustNimbusError as error:
        raise CannotConnect from error

    return {"name": "JustNimbus"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JustNimbus."""

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

        await self.async_set_unique_id(user_input[CONF_CLIENT_ID])
        self._abort_if_unique_id_configured()

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidClientId:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> JustNimbusOptionFlow:
        """Get the options flow for this handler."""
        return JustNimbusOptionFlow(config_entry)


class JustNimbusOptionFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    scan_interval: scan_interval_options,
                }
            ),
        )

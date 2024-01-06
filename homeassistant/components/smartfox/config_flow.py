"""Config flow for Smartfox integration."""
from __future__ import annotations

import logging
from typing import Any

from smartfox import Smartfox
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_BATTERY_ENABLED,
    CONF_CAR_CHARGER_ENABLED,
    CONF_HEAT_PUMP_ENABLED,
    CONF_HOST,
    CONF_INTEVAL,
    CONF_NAME,
    CONF_PORT,
    CONF_SCHEME,
    CONF_VERIFY,
    CONF_WATER_SENSORS_ENABLED,
    DEFAULT_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCHEME,
    DEFAULT_VERIFY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_SCHEME, default=DEFAULT_SCHEME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_VERIFY, default=DEFAULT_VERIFY): bool,
        vol.Required(CONF_VERIFY, default=DEFAULT_VERIFY): bool,
        vol.Required(CONF_INTEVAL, default=DEFAULT_INTERVAL): int,
        vol.Required(CONF_CAR_CHARGER_ENABLED, default=False): bool,
        vol.Required(CONF_HEAT_PUMP_ENABLED, default=False): bool,
        vol.Required(CONF_WATER_SENSORS_ENABLED, default=False): bool,
        vol.Required(CONF_BATTERY_ENABLED, default=False): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    smartfox = Smartfox(
        scheme=str(data[CONF_SCHEME]),
        host=str(data[CONF_HOST]),
        port=int(data[CONF_PORT]),
        verify=bool(data[CONF_VERIFY]),
    )

    await hass.async_add_executor_job(smartfox.getValues)

    # Return info that you want to store in the config entry.
    return {"title": f"{str(data[CONF_NAME])}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smartfox."""

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
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

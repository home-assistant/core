"""Config flow for Starlink integration."""
from __future__ import annotations

import logging
from typing import Any

from spacex.starlink import CommunicationError
from spacex.starlink.dish import StarlinkDish
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEFAULT_ADDRESS,
    CONF_DEFAULT_NAME,
    CONF_DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=CONF_DEFAULT_NAME): cv.string,
        vol.Required(CONF_ADDRESS, default=CONF_DEFAULT_ADDRESS): cv.string,
        vol.Required(
            CONF_SCAN_INTERVAL, default=CONF_DEFAULT_SCAN_INTERVAL
        ): cv.positive_float,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    dish = StarlinkDish(address=data[CONF_ADDRESS])
    try:
        # TODO: Can I make this async?
        dish.connect()
    except CommunicationError:
        raise CannotConnect()

    # Return info that you want to store in the config entry.
    return {"title": "Starlink"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Starlink."""

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

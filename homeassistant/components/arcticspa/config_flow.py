"""Config flow for Arctic Spa integration."""
from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_ARCTIC_SPA_KEY_NAME, DOMAIN
from .hottub import Device

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=CONF_ARCTIC_SPA_KEY_NAME): str,
        vol.Required(CONF_API_KEY): str,
    }
)


def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    device = Device(data[CONF_API_KEY])

    code = device.authenticate()
    match code:
        case HTTPStatus.OK:
            # Return info that you want to store in the config entry.
            return {CONF_NAME: data[CONF_NAME], "id": device.id}
        case HTTPStatus.UNAUTHORIZED:
            raise InvalidAuth
        case HTTPStatus.TOO_MANY_REQUESTS:
            raise TooManyRequests
        case _:
            _LOGGER.exception("Unexpected error code %d", code)
            raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Arctic Spa."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except TooManyRequests:
                errors["base"] = "too_many_requests"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class TooManyRequests(HomeAssistantError):
    """Error to indicate we tried too many times."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

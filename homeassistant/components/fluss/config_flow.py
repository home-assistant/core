"""Config flow for Fluss+ integration."""

from __future__ import annotations

import logging
from typing import Any

from fluss_api import FlussApiClient, FlussApiClientCommunicationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): cv.string})


class ApiKeyStorageHub:
    """ApiKeyStorageHub class to store APIs."""

    def __init__(self, apikey: str) -> None:
        """Initialize."""
        self.apikey = apikey

    async def authenticate(self) -> bool:  # noqa: D102
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    api = FlussApiClient(data[CONF_API_KEY], hass)
    try:
        is_valid = await api.async_validate_api_key()

        if not is_valid:
            raise InvalidAuth
    except FlussApiClientCommunicationError:
        raise CannotConnect  # noqa: B904

    return {"title": "Fluss+"}


class FlussConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fluss+."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=info.get("title", "Fluss Device"), data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as ex:
                _LOGGER.exception("Unexpected exception:  %s", ex)  # noqa: TRY401
                errors["base"] = "unknown"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_API_KEY): str,
                        }
                    ),
                    errors=errors,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

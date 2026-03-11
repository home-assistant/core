"""Config flow for LoJack integration."""

from __future__ import annotations

import logging
from typing import Any

from lojack_api import ApiError, AuthenticationError, LoJackClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Returns the unique user ID from the API.
    """
    try:
        async with await LoJackClient.create(
            data[CONF_USERNAME], data[CONF_PASSWORD]
        ) as client:
            if client.user_id is None:
                raise CannotConnect("API did not return a user identifier")
            return client.user_id
    except AuthenticationError as err:
        raise InvalidAuth(f"Invalid username or password: {err}") from err
    except ApiError as err:
        raise CannotConnect(f"API error: {err}") from err


class LoJackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LoJack."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_id = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"LoJack ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""

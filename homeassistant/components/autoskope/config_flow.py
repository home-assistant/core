"""Config flow for the Autoskope integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from autoskope_client.api import AutoskopeApi
from autoskope_client.models import CannotConnect, InvalidAuth
from homeassistant.config_entries import ConfigFlow as ConfigFlowBase, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data.get(CONF_HOST, DEFAULT_HOST)

    try:
        async with AutoskopeApi(
            host=host,
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
        ):
            # If we get here, connection and authentication succeeded
            pass

    except InvalidAuth as err:
        _LOGGER.warning("Authentication failed during validation: %s", err)
        raise InvalidAuth("Authentication failed") from err
    except CannotConnect as err:
        _LOGGER.warning("Connection failed during validation: %s", err)
        raise CannotConnect(f"Connection error: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation")
        raise CannotConnect(f"Unexpected validation error: {err}") from err

    return {"title": f"Autoskope ({data[CONF_USERNAME]})"}


class AutoskopeConfigFlow(ConfigFlowBase, domain=DOMAIN):
    """Handle a config flow for Autoskope."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = (
                f"{user_input[CONF_USERNAME]}@{user_input.get(CONF_HOST, DEFAULT_HOST)}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates=user_input)

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

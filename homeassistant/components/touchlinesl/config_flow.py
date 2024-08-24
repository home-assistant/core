"""Config flow for Roth Touchline SL integration."""

from __future__ import annotations

import logging
from typing import Any

from pytouchlinesl import Module, TouchlineSL
from pytouchlinesl.client import RothAPIError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector

from .const import CONF_MODULE, CONFIG_ENTRY_VERSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_user_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    account = TouchlineSL(username=data[CONF_USERNAME], password=data[CONF_PASSWORD])
    try:
        await account.modules()
    except RothAPIError as e:
        if e.status == 401:
            raise InvalidAuth from e
        raise CannotConnect from e


class TouchlineSLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline SL."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        """Construct a new ConfigFlow for the Roth Touchline SL module."""
        self.account = None
        self.data: dict[str, str] = {}
        self.modules: list[Module] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step that gathers username and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_user_input(self.hass, user_input)
                self.data.update(user_input)
                return await self.async_step_module(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_module(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Present the user with a list of modules associated with their account."""

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)
            module_id = user_input.get(CONF_MODULE)
            self.data.update(user_input)

            if username and password:
                self.account = TouchlineSL(username=username, password=password)
                assert isinstance(self.account, TouchlineSL)
                self.modules = await self.account.modules()

            if module_id:
                return self.async_create_entry(
                    title=self.data[CONF_USERNAME], data=self.data
                )

        data_schema = {
            CONF_MODULE: selector(
                {
                    "select": {
                        "options": [
                            {"label": s.name, "value": s.id} for s in self.modules
                        ]
                    }
                }
            )
        }

        return self.async_show_form(
            step_id="module", data_schema=vol.Schema(data_schema)
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

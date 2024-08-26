"""Config flow for Roth Touchline SL integration."""

from __future__ import annotations

import logging
from typing import Any

from pytouchlinesl import Module, TouchlineSL
from pytouchlinesl.client import RothAPIError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONFIG_ENTRY_VERSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


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
                username: str = user_input.get(CONF_USERNAME, "")
                password: str = user_input.get(CONF_PASSWORD, "")
                account = TouchlineSL(username=username, password=password)
                await account.modules()

                self.data.update(user_input)
                return self.async_create_entry(title=username, data=self.data)
            except RothAPIError as e:
                if e.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

"""Config flow for Local To-do integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.util import slugify

from .const import CONF_STORAGE_KEY, CONF_TODO_LIST_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TODO_LIST_NAME): str,
    }
)


class LocalTodoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local To-do."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key = slugify(user_input[CONF_TODO_LIST_NAME])
            self._async_abort_entries_match({CONF_STORAGE_KEY: key})
            user_input[CONF_STORAGE_KEY] = key
            return self.async_create_entry(
                title=user_input[CONF_TODO_LIST_NAME], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

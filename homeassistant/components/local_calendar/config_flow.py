"""Config flow for Local Calendar integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_CALENDAR_NAME,
    CONF_ICS_FILE,
    CONF_IMPORT_ICS,
    CONF_STORAGE_KEY,
    DOMAIN,
)
from .helpers.ics import save_uploaded_ics_file

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_NAME): str,
        vol.Optional(CONF_IMPORT_ICS): bool,
    }
)

STEP_IMPORT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ICS_FILE): selector.FileSelector(
            config=selector.FileSelectorConfig(accept=".ics")
        ),
    }
)


class LocalCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local Calendar."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        key = slugify(user_input[CONF_CALENDAR_NAME])
        self._async_abort_entries_match({CONF_STORAGE_KEY: key})
        user_input[CONF_STORAGE_KEY] = key
        if user_input.get(CONF_IMPORT_ICS):
            self.data = user_input
            return await self.async_step_import()
        return self.async_create_entry(
            title=user_input[CONF_CALENDAR_NAME], data=user_input
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle optional iCal (.ics) import."""
        if user_input is None:
            return self.async_show_form(
                step_id="import", data_schema=STEP_IMPORT_DATA_SCHEMA
            )

        await save_uploaded_ics_file(
            self.hass, user_input[CONF_ICS_FILE], self.data[CONF_STORAGE_KEY]
        )
        return self.async_create_entry(
            title=self.data[CONF_CALENDAR_NAME], data=self.data
        )

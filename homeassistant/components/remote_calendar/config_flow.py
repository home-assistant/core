"""Config flow for Local Calendar integration."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
from typing import Any

from ical.calendar_stream import CalendarStream
from ical.exceptions import CalendarParseError
import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    ATTR_IMPORT_ICS_FILE,
    CONF_CALENDAR_NAME,
    CONF_ICS_FILE,
    CONF_STORAGE_KEY,
    DOMAIN,
    STORAGE_PATH,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.const import CONF_URL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_CALENDAR_NAME): str, vol.Required(CONF_URL): str}
)


class RemoteCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local Calendar."""

    VERSION = 1

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
        _LOGGER.debug("User input: %s", user_input)
        key = slugify(user_input[CONF_CALENDAR_NAME])
        user_input[CONF_STORAGE_KEY] = key
        self.data = user_input
        errors = {}
        client = get_async_client(self.hass)
        _LOGGER.debug("User input in fetch url: %s", user_input)
        if user_input is not None:
            headers = {}
            try:
                await client.get(user_input[CONF_URL], headers=headers)
            except ValueError as err:
                _LOGGER.debug("Error saving uploaded file: %s", err)
            else:
                return self.async_create_entry(
                    title=self.data[CONF_CALENDAR_NAME], data=self.data
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
        )

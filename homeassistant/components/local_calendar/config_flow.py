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
    ATTR_CREATE_EMPTY,
    ATTR_IMPORT_ICS_FILE,
    CONF_CALENDAR_NAME,
    CONF_ICS_FILE,
    CONF_IMPORT,
    CONF_STORAGE_KEY,
    DOMAIN,
    STORAGE_PATH,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_NAME): str,
        vol.Optional(CONF_IMPORT, default=ATTR_CREATE_EMPTY): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    ATTR_CREATE_EMPTY,
                    ATTR_IMPORT_ICS_FILE,
                ],
                translation_key=CONF_IMPORT,
            )
        ),
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
        if user_input.get(CONF_IMPORT) == ATTR_IMPORT_ICS_FILE:
            self.data = user_input
            return await self.async_step_import_ics_file()
        return self.async_create_entry(
            title=user_input[CONF_CALENDAR_NAME],
            data=user_input,
        )

    async def async_step_import_ics_file(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle optional iCal (.ics) import."""
        errors = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    save_uploaded_ics_file,
                    self.hass,
                    user_input[CONF_ICS_FILE],
                    self.data[CONF_STORAGE_KEY],
                )
            except HomeAssistantError as err:
                _LOGGER.debug("Error saving uploaded file: %s", err)
                errors[CONF_ICS_FILE] = "invalid_ics_file"
            else:
                return self.async_create_entry(
                    title=self.data[CONF_CALENDAR_NAME], data=self.data
                )

        return self.async_show_form(
            step_id="import_ics_file",
            data_schema=STEP_IMPORT_DATA_SCHEMA,
            errors=errors,
        )


def save_uploaded_ics_file(
    hass: HomeAssistant, uploaded_file_id: str, storage_key: str
):
    """Validate the uploaded file and move it to the storage directory."""

    with process_uploaded_file(hass, uploaded_file_id) as file:
        ics = file.read_text(encoding="utf8")
        try:
            CalendarStream.from_ics(ics)
        except CalendarParseError as err:
            raise HomeAssistantError("Failed to upload file: Invalid ICS file") from err
        dest_path = Path(hass.config.path(STORAGE_PATH.format(key=storage_key)))
        shutil.move(file, dest_path)

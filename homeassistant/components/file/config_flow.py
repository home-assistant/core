"""Config flow for file integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_FILE_PATH,
    CONF_FILENAME,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
)
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME, DOMAIN

FILE_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILE_PATH): cv.isfile,
        vol.Optional(CONF_NAME, default="File"): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


class FileConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a file config flow."""

    VERSION = 1

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import `file`` config from configuration.yaml."""
        assert import_data is not None
        platform = import_data[CONF_PLATFORM]
        name: str = import_data.get(CONF_NAME, DEFAULT_NAME)
        file_name: str
        if platform == Platform.NOTIFY:
            file_name = import_data[CONF_FILENAME]
        else:
            file_name = import_data[CONF_FILE_PATH]
        title = f"{name} [{file_name}]"
        return self.async_create_entry(title=title, data=import_data)

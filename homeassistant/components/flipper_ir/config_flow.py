"""Config flow for the Flipper IR integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import CONF_COMMANDS, CONF_IR_FILE, DOMAIN
from .parser import InvalidIRFileError, parse_ir_file

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_IR_FILE): selector.FileSelector(
            config=selector.FileSelectorConfig(accept=".ir,text/plain")
        ),
    }
)


class FlipperIRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flipper IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                commands = await self.hass.async_add_executor_job(
                    _read_uploaded_ir_file, self.hass, user_input[CONF_IR_FILE]
                )
            except InvalidIRFileError as err:
                _LOGGER.error("Invalid IR file: %s", err)
                errors[CONF_IR_FILE] = "invalid_ir_file"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_COMMANDS: commands,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


def _read_uploaded_ir_file(
    hass: HomeAssistant, uploaded_file_id: str
) -> list[dict[str, str]]:
    """Read and parse the uploaded Flipper IR file."""
    with process_uploaded_file(hass, uploaded_file_id) as path:
        content = path.read_text(encoding="utf8")
    return parse_ir_file(content)

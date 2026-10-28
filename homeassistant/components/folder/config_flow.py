"""Config flow for the Folder integration."""

from collections.abc import Mapping
import os
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FILTER, CONF_FOLDER_PATHS, DEFAULT_FILTER, DOMAIN


def validate_path(hass: HomeAssistant, path: str) -> str | None:
    """Return an error key if the folder can't be monitored."""
    if not os.path.isdir(path):
        return "not_dir"
    if not os.access(path, os.R_OK):
        return "not_readable_dir"
    if not hass.config.is_allowed_path(path):
        return "not_allowed_dir"
    return None


async def validate_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Check the path is a folder that is allowed to be monitored."""
    hass = handler.parent_handler.hass
    path = os.path.expanduser(user_input[CONF_FOLDER_PATHS])
    if error := await hass.async_add_executor_job(validate_path, hass, path):
        raise SchemaFlowError(error)
    handler.parent_handler._async_abort_entries_match(  # noqa: SLF001
        {CONF_FOLDER_PATHS: path, CONF_FILTER: user_input[CONF_FILTER]}
    )
    return {**user_input, CONF_FOLDER_PATHS: path}


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Check no other entry monitors the folder with the same filter."""
    handler.parent_handler._async_abort_entries_match(  # noqa: SLF001
        {
            CONF_FOLDER_PATHS: handler.options[CONF_FOLDER_PATHS],
            CONF_FILTER: user_input[CONF_FILTER],
        }
    )
    return user_input


OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_FILTER, default=DEFAULT_FILTER): TextSelector(),
    }
)
DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_FOLDER_PATHS): TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(schema=DATA_SCHEMA, validate_user_input=validate_setup),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        schema=OPTIONS_SCHEMA, validate_user_input=validate_options
    ),
}


class FolderConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Folder."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_FOLDER_PATHS]

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle the import of a YAML sensor platform configuration."""
        data = {
            CONF_FOLDER_PATHS: import_data[CONF_FOLDER_PATHS],
            CONF_FILTER: import_data[CONF_FILTER],
        }
        if error := await self.hass.async_add_executor_job(
            validate_path, self.hass, data[CONF_FOLDER_PATHS]
        ):
            return self.async_abort(reason=error)
        self._async_abort_entries_match(data)
        return self.async_create_entry(data=data)

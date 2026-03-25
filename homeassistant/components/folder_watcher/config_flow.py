"""Adds config flow for Folder watcher."""

from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import CONF_FOLDER, CONF_PATTERNS, DEFAULT_PATTERN, DOMAIN


async def validate_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Check path is a folder."""
    value: str = user_input[CONF_FOLDER]
    dir_in = os.path.expanduser(str(value))
    handler.parent_handler._async_abort_entries_match({CONF_FOLDER: value})  # noqa: SLF001

    if not os.path.isdir(dir_in):
        raise SchemaFlowError("not_dir")
    if not os.access(dir_in, os.R_OK):
        raise SchemaFlowError("not_readable_dir")
    if not handler.parent_handler.hass.config.is_allowed_path(value):
        raise SchemaFlowError("not_allowed_dir")

    return user_input


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PATTERNS, default=[DEFAULT_PATTERN]): SelectSelector(
            SelectSelectorConfig(
                options=[DEFAULT_PATTERN],
                multiple=True,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FOLDER): TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(schema=DATA_SCHEMA, validate_user_input=validate_setup),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(schema=OPTIONS_SCHEMA),
}


class FolderWatcherConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Folder Watcher."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return f"Folder Watcher {options[CONF_FOLDER]}"

    @callback
    def async_create_entry(
        self, data: Mapping[str, Any], **kwargs: Any
    ) -> ConfigFlowResult:
        """Finish config flow and create a config entry."""
        self._async_abort_entries_match({CONF_FOLDER: data[CONF_FOLDER]})
        return super().async_create_entry(data, **kwargs)

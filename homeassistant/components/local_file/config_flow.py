"""Config flow for Local file."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, override

import probatio

from homeassistant.const import CONF_FILE_PATH
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import TextSelector

from .const import DEFAULT_NAME, DOMAIN
from .util import check_file_path_access


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""
    file_path: str = user_input[CONF_FILE_PATH]
    if not await handler.parent_handler.hass.async_add_executor_job(
        check_file_path_access, file_path
    ):
        raise SchemaFlowError("not_readable_path")

    handler.parent_handler._async_abort_entries_match(  # noqa: SLF001
        {CONF_FILE_PATH: user_input[CONF_FILE_PATH]}
    )

    return user_input


DATA_SCHEMA_OPTIONS = probatio.Schema(
    {
        probatio.Required(CONF_FILE_PATH): TextSelector(),
    }
)
CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_OPTIONS, validate_user_input=validate_options
    )
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS, validate_user_input=validate_options
    )
}


class LocalFileConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Local file."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return Path(options[CONF_FILE_PATH]).stem or DEFAULT_NAME

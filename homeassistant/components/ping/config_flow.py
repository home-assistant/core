"""Config flow for Ping (ICMP) integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to platform."""
    return cast(str, options["platform_type"])


def set_platform(
    platform: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]
]:
    """Set platform type."""

    async def _set_platform(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Add platform type to user input."""
        return {"platform_type": platform, **user_input}

    return _set_platform


BINARY_SENSOR_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(
            CONF_PING_COUNT, default=DEFAULT_PING_COUNT
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=100, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)

BINARY_SENSOR_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(BINARY_SENSOR_OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(["binary_sensor"]),
    "binary_sensor": SchemaFlowFormStep(
        BINARY_SENSOR_CONFIG_SCHEMA,
        validate_user_input=set_platform("binary_sensor"),
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    "binary_sensor": SchemaFlowFormStep(BINARY_SENSOR_OPTIONS_SCHEMA),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Times of the Day."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])

    async def async_step_import(self, import_info: Mapping[str, Any]) -> FlowResult:
        """Import a entry."""

        if CONF_HOST in import_info:
            # import data seems to be a binary_sensor entry
            self._async_abort_entries_match({CONF_HOST: import_info[CONF_HOST]})
            return self.async_create_entry(
                data={"platform_type": "binary_sensor", **import_info}
            )

        return self.async_abort(reason="No matching type")

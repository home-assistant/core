"""Adds config flow for System Monitor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import slugify

from .const import CONF_PROCESS, DOMAIN
from .util import get_all_running_processes


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: dict[str, list] = handler.options.setdefault(BINARY_SENSOR_DOMAIN, {})
    processes = sensors.setdefault(CONF_PROCESS, [])
    previous_processes = processes.copy()
    processes.clear()
    processes.extend(user_input[CONF_PROCESS])

    entity_registry = er.async_get(handler.parent_handler.hass)
    for process in previous_processes:
        if process not in processes and (
            entity_id := entity_registry.async_get_entity_id(
                BINARY_SENSOR_DOMAIN, DOMAIN, slugify(f"binary_process_{process}")
            )
        ):
            entity_registry.async_remove(entity_id)

    return {}


async def get_sensor_setup_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return process sensor setup schema."""
    hass = handler.parent_handler.hass
    processes = list(await hass.async_add_executor_job(get_all_running_processes, hass))
    return vol.Schema(
        {
            vol.Required(CONF_PROCESS): SelectSelector(
                SelectSelectorConfig(
                    options=processes,
                    multiple=True,
                    custom_value=True,
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            )
        }
    )


async def get_suggested_value(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    """Return suggested values for sensor setup."""
    sensors: dict[str, list] = handler.options.get(BINARY_SENSOR_DOMAIN, {})
    processes: list[str] = sensors.get(CONF_PROCESS, [])
    return {CONF_PROCESS: processes}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(schema=vol.Schema({})),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        get_sensor_setup_schema,
        suggested_values=get_suggested_value,
        validate_user_input=validate_sensor_setup,
    )
}


class SystemMonitorConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for System Monitor."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    VERSION = 1
    MINOR_VERSION = 3

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "System Monitor"

    @callback
    def async_create_entry(
        self, data: Mapping[str, Any], **kwargs: Any
    ) -> ConfigFlowResult:
        """Finish config flow and create a config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return super().async_create_entry(data, **kwargs)

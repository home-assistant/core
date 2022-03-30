"""Config flow for Time & Date integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowFormStep,
    HelperFlowMenuStep,
)
from homeassistant.helpers.selector import selector

from .const import (
    CONF_DATE,
    CONF_DATE_TIME,
    CONF_DATE_TIME_ISO,
    CONF_DATE_TIME_UTC,
    CONF_DISPLAY_OPTION,
    CONF_TIME,
    CONF_TIME_DATE,
    CONF_TIME_UTC,
    DOMAIN,
    OPTION_TYPES,
)

OPTION_SELECT_TYPES = [
    {"value": CONF_DATE, "label": "Local Date"},
    {"value": CONF_TIME, "label": "Local Time"},
    {"value": CONF_TIME_UTC, "label": "UTC Time"},
    {"value": CONF_DATE_TIME, "label": "Local Date + Time"},
    {"value": CONF_TIME_DATE, "label": "Local Time + Date"},
    {"value": CONF_DATE_TIME_ISO, "label": "Local Date + Time (ISO formatted)"},
    {"value": CONF_DATE_TIME_UTC, "label": "UTC Date + Time"},
]

CONFIG_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DISPLAY_OPTION, default=CONF_TIME): selector(
            {"select": {"options": OPTION_SELECT_TYPES}}
        ),
    }
)

CONFIG_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "user": HelperFlowFormStep(CONFIG_OPTIONS_SCHEMA)
}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Time & Date."""

    config_flow = CONFIG_FLOW
    singleton = True

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return OPTION_TYPES[options[CONF_DISPLAY_OPTION]]

    @callback
    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Take necessary actions after the config flow is finished, if needed."""
        unique_id = options[CONF_DISPLAY_OPTION]
        self.async_set_unique_id_cb(unique_id)
        self._abort_if_unique_id_configured()

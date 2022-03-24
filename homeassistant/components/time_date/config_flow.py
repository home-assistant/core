"""Config flow for Time & Date integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DISPLAY_OPTIONS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowFormStep,
    HelperFlowMenuStep,
)
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BEAT,
    CONF_DATE,
    CONF_DATE_TIME,
    CONF_DATE_TIME_ISO,
    CONF_DATE_TIME_UTC,
    CONF_TIME,
    CONF_TIME_DATE,
    CONF_TIME_UTC,
    DOMAIN,
)

CONFIG_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BEAT, default=False): selector({"boolean": {}}),
        vol.Required(CONF_DATE, default=False): selector({"boolean": {}}),
        vol.Required(CONF_DATE_TIME, default=False): selector({"boolean": {}}),
        vol.Required(CONF_DATE_TIME_ISO, default=False): selector({"boolean": {}}),
        vol.Required(CONF_DATE_TIME_UTC, default=False): selector({"boolean": {}}),
        vol.Required(CONF_TIME, default=False): selector({"boolean": {}}),
        vol.Required(CONF_TIME_DATE, default=False): selector({"boolean": {}}),
        vol.Required(CONF_TIME_UTC, default=False): selector({"boolean": {}}),
    }
)


CONFIG_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "user": HelperFlowFormStep(CONFIG_OPTIONS_SCHEMA)
}

OPTIONS_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "init": HelperFlowFormStep(CONFIG_OPTIONS_SCHEMA)
}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Time & Date."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    singleton = True

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "Time & Date"

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        imported = {
            CONF_BEAT: CONF_BEAT in user_input[CONF_DISPLAY_OPTIONS],
            CONF_DATE: CONF_DATE in user_input[CONF_DISPLAY_OPTIONS],
            CONF_DATE_TIME: CONF_DATE_TIME in user_input[CONF_DISPLAY_OPTIONS],
            CONF_DATE_TIME_ISO: CONF_DATE_TIME_ISO in user_input[CONF_DISPLAY_OPTIONS],
            CONF_DATE_TIME_UTC: CONF_DATE_TIME_UTC in user_input[CONF_DISPLAY_OPTIONS],
            CONF_TIME: CONF_TIME in user_input[CONF_DISPLAY_OPTIONS],
            CONF_TIME_DATE: CONF_TIME_DATE in user_input[CONF_DISPLAY_OPTIONS],
            CONF_TIME_UTC: CONF_TIME_UTC in user_input[CONF_DISPLAY_OPTIONS],
        }
        return await self.async_step_user(imported)

"""Adds config flow for Scrape integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_INDEX, CONF_SELECT, DEFAULT_NAME, DEFAULT_VERIFY_SSL, DOMAIN

SCHEMA_SETUP = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
    vol.Required(CONF_RESOURCE): TextSelector(
        TextSelectorConfig(type=TextSelectorType.URL)
    ),
    vol.Required(CONF_SELECT): TextSelector(),
}

SCHEMA_OPT = {
    vol.Optional(CONF_ATTRIBUTE): TextSelector(),
    vol.Optional(CONF_INDEX, default=0): NumberSelector(
        NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
    ),
    vol.Optional(CONF_AUTHENTICATION): SelectSelector(
        SelectSelectorConfig(
            options=[HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION],
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Optional(CONF_USERNAME): TextSelector(),
    vol.Optional(CONF_PASSWORD): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_HEADERS): ObjectSelector(),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): TextSelector(),
    vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[e.value for e in SensorDeviceClass],
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Optional(CONF_STATE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[e.value for e in SensorStateClass],
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): BooleanSelector(),
}

DATA_SCHEMA = vol.Schema({**SCHEMA_SETUP, **SCHEMA_OPT})
DATA_SCHEMA_OPT = vol.Schema({**SCHEMA_OPT})

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(DATA_SCHEMA),
    "import": SchemaFlowFormStep(DATA_SCHEMA),
}
OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(DATA_SCHEMA_OPT),
}


class ScrapeConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Scrape."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]

    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Check for duplicate records."""
        data: dict[str, Any] = dict(options)
        self._async_abort_entries_match(data)


class ScrapeOptionsFlowHandler(SchemaOptionsFlowHandler):
    """Handle a config flow for Scrape."""

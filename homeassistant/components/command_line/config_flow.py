"""The command_line config flow."""
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
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
)

from .const import DOMAIN
from .schema import (
    DATA_SENSOR,
    DATA_BINARY_SENSOR,
    DATA_COVER,
    DATA_NOTIFY,
    DATA_SWITCH,
    DATA_COMMON,
    DATA_UNIQUE_ID,
)

DATA_SCHEMA_SENSOR = vol.Schema(DATA_COMMON).extend(DATA_SENSOR)
DATA_SCHEMA_BINARY_SENSOR = vol.Schema(DATA_COMMON).extend(DATA_BINARY_SENSOR)
DATA_SCHEMA_COVER = vol.Schema(DATA_COMMON).extend(DATA_COVER)
DATA_SCHEMA_NOTIFY = vol.Schema(DATA_COMMON).extend(DATA_NOTIFY)
DATA_SCHEMA_SWITCH = vol.Schema(DATA_COMMON).extend(DATA_SWITCH)
DATA_SCHEMA_SENSOR_OPT = vol.Schema(DATA_SENSOR)
DATA_SCHEMA_BINARY_SENSOR_OPT = vol.Schema(DATA_BINARY_SENSOR)
DATA_SCHEMA_COVER_OPT = vol.Schema(DATA_NOTIFY)
DATA_SCHEMA_NOTIFY_OPT = vol.Schema(DATA_SWITCH)
DATA_SCHEMA_SWITCH_OPT = vol.Schema(DATA_COMMON)

CONFIG_MENU_OPTIONS = ["sensor", "binary_sensor", "cover", "notify", "switch"]

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowMenuStep(CONFIG_MENU_OPTIONS),
    "sensor": SchemaFlowFormStep(DATA_SCHEMA_SENSOR),
    "binary_sensor": SchemaFlowFormStep(DATA_SCHEMA_BINARY_SENSOR),
    "cover": SchemaFlowFormStep(DATA_SCHEMA_COVER),
    "notify": SchemaFlowFormStep(DATA_SCHEMA_NOTIFY),
    "switch": SchemaFlowFormStep(DATA_SCHEMA_SWITCH),
    "import": SchemaFlowFormStep(DATA_SCHEMA_SENSOR),
}
OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(DATA_SCHEMA_OPTIONS),
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

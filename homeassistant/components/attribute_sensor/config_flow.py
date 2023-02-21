"""Config flow for Min/Max integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEVICE_CLASS,
    CONF_SOURCE_ENTITY,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(),
        ),
        vol.Required(CONF_ATTRIBUTE_NAME): str,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Attribute Sensor."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])

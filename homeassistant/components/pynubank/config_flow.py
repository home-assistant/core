"""Config flow for nu integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("name"): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA)
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
}

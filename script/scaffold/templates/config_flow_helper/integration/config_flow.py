"""Config flow for NEW_NAME integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowFormStep,
    HelperFlowMenuStep,
)

from .const import DOMAIN

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.selector(
            {"entity": {"domain": "sensor"}}
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("name"): selector.selector({"text": {}}),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "user": HelperFlowFormStep(CONFIG_SCHEMA)
}

OPTIONS_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "init": HelperFlowFormStep(OPTIONS_SCHEMA)
}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for NEW_NAME."""

    config_flow = CONFIG_FLOW
    # TODO remove the options_flow if the integration does not have an options flow
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""

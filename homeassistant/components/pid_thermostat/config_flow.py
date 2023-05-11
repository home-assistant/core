"""Config flow for pid integration."""
from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.pid_controller.config_flow import (
    CONF_CYCLE_TIME,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    AC_MODE_COOL,
    AC_MODE_HEAT,
    CONF_AC_MODE,
    CONF_HEATER,
    CONF_SENSOR,
    DEFAULT_AC_MODE,
    DEFAULT_CYCLE_TIME,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_AC_MODES = [
    selector.SelectOptionDict(value=AC_MODE_HEAT, label="Heat"),
    selector.SelectOptionDict(value=AC_MODE_COOL, label="Cool"),
]

OPTIONS_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HEATER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[NUMBER_DOMAIN]),
        ),
        vol.Required(CONF_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN]),
        ),
        vol.Optional(CONF_AC_MODE, default=DEFAULT_AC_MODE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_AC_MODES, translation_key=CONF_AC_MODE
            ),
        ),
        vol.Optional(CONF_PID_KI, default=DEFAULT_PID_KI): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, step=0.01, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Optional(CONF_PID_KP, default=DEFAULT_PID_KP): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, step=0.001, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Optional(CONF_PID_KD, default=DEFAULT_PID_KD): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, step=0.001, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Optional(
            CONF_CYCLE_TIME, default=DEFAULT_CYCLE_TIME
        ): selector.DurationSelector(),
    }
)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_BASE_SCHEMA.schema)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_BASE_SCHEMA),
}


class PIDControllerPWMConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """PID thermostat Config handler."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if CONF_NAME in options else ""

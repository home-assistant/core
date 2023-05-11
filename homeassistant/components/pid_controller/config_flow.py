"""Config flow for pid integration."""
from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_MAXIMUM, CONF_MINIMUM, CONF_MODE, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_CYCLE_TIME,
    CONF_INPUT1,
    CONF_INPUT2,
    CONF_OUTPUT,
    CONF_PID_DIR,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_STEP,
    DEFAULT_CYCLE_TIME,
    DEFAULT_MODE,
    DEFAULT_PID_DIR,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DOMAIN,
    MODE_AUTO,
    MODE_BOX,
    MODE_SLIDER,
    PID_DIR_DIRECT,
    PID_DIR_REVERSE,
)

_LOGGER = logging.getLogger(__name__)


_MODES = [
    selector.SelectOptionDict(value=MODE_AUTO, label="Auto"),
    selector.SelectOptionDict(value=MODE_BOX, label="Box"),
    selector.SelectOptionDict(value=MODE_SLIDER, label="Slider"),
]

_PID_DIRECTIONS = [
    selector.SelectOptionDict(value=PID_DIR_DIRECT, label="Direct"),
    selector.SelectOptionDict(value=PID_DIR_REVERSE, label="Reverse"),
]

OPTIONS_BASE_SCHEMA_PART1 = vol.Schema(
    {
        vol.Required(CONF_OUTPUT): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[NUMBER_DOMAIN]),
        ),
        vol.Required(CONF_INPUT1): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN]),
        ),
    }
)


OPTIONS_BASE_SCHEMA_PART2 = vol.Schema(
    {
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
        vol.Optional(CONF_PID_DIR, default=DEFAULT_PID_DIR): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_PID_DIRECTIONS, translation_key=CONF_PID_DIR
            ),
        ),
        vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN_VALUE): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, mode=selector.NumberSelectorMode.BOX),
        ),
        vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX_VALUE): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, mode=selector.NumberSelectorMode.BOX),
        ),
        vol.Optional(
            CONF_CYCLE_TIME, default=DEFAULT_CYCLE_TIME
        ): selector.DurationSelector(),
        vol.Optional(CONF_STEP, default=DEFAULT_STEP): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_MODES),
        ),
    }
)

OPTIONS_BASE_SCHEMA = OPTIONS_BASE_SCHEMA_PART1.extend(OPTIONS_BASE_SCHEMA_PART2.schema)

OPTIONS_PID_SCHEMA = OPTIONS_BASE_SCHEMA_PART1.extend(
    vol.Schema(
        {
            vol.Optional(CONF_INPUT2): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN])
            ),
        }
    ).schema
).extend(OPTIONS_BASE_SCHEMA_PART2.schema)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_PID_SCHEMA.schema)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_PID_SCHEMA),
}


class PIDControllerPWMConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """PID regulator Config handler."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if CONF_NAME in options else ""

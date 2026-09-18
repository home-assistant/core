"""Config flow for Generic hygrostat."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, cast, override

import probatio

from homeassistant.components import fan, switch
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import CONF_NAME, DEGREE
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import (
    CONF_AC_MODE,
    CONF_COLD_TOLERANCE,
    CONF_DUR_COOLDOWN,
    CONF_HEATER,
    CONF_HOT_TOLERANCE,
    CONF_KEEP_ALIVE,
    CONF_MAX_DUR,
    CONF_MAX_TEMP,
    CONF_MIN_DUR,
    CONF_MIN_TEMP,
    CONF_PRESETS,
    CONF_SENSOR,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

OPTIONS_SCHEMA = {
    probatio.Required(CONF_AC_MODE): selector.BooleanSelector(
        selector.BooleanSelectorConfig(),
    ),
    probatio.Required(CONF_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.TEMPERATURE
        )
    ),
    probatio.Required(CONF_HEATER): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=[fan.DOMAIN, switch.DOMAIN])
    ),
    probatio.Required(
        CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
    probatio.Required(
        CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
    probatio.Optional(CONF_MIN_DUR): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False)
    ),
    probatio.Optional(CONF_KEEP_ALIVE): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False)
    ),
    probatio.Optional(CONF_MAX_DUR): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False)
    ),
    probatio.Optional(CONF_DUR_COOLDOWN): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False)
    ),
    probatio.Optional(CONF_MIN_TEMP): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
    probatio.Optional(CONF_MAX_TEMP): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
}

PRESETS_SCHEMA = {
    probatio.Optional(v): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    )
    for v in CONF_PRESETS.values()
}

CONFIG_SCHEMA = {
    probatio.Required(CONF_NAME): selector.TextSelector(),
    **OPTIONS_SCHEMA,
}


async def _validate_config(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate config."""
    if all(x in user_input for x in (CONF_MIN_DUR, CONF_MAX_DUR)):
        min_cycle = timedelta(**user_input[CONF_MIN_DUR])
        max_cycle = timedelta(**user_input[CONF_MAX_DUR])

        if min_cycle >= max_cycle:
            raise SchemaFlowError("min_max_runtime")

    return user_input


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        probatio.Schema(CONFIG_SCHEMA),
        validate_user_input=_validate_config,
        next_step="presets",
    ),
    "presets": SchemaFlowFormStep(probatio.Schema(PRESETS_SCHEMA)),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        probatio.Schema(OPTIONS_SCHEMA),
        validate_user_input=_validate_config,
        next_step="presets",
    ),
    "presets": SchemaFlowFormStep(probatio.Schema(PRESETS_SCHEMA)),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow."""

    MINOR_VERSION = 3

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])

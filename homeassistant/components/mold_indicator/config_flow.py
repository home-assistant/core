"""Config flow for Mold indicator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME, Platform
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
    DOMAIN,
)


async def validate_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate already existing entry."""
    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001
    if user_input[CONF_CALIBRATION_FACTOR] == 0.0:
        raise SchemaFlowError("calibration_is_zero")
    return user_input


DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Required(CONF_CALIBRATION_FACTOR): NumberSelector(
            NumberSelectorConfig(step=0.1, mode=NumberSelectorMode.BOX)
        )
    }
)

DATA_SCHEMA_CONFIG = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_INDOOR_TEMP): EntitySelector(
            EntitySelectorConfig(
                domain=Platform.SENSOR, device_class=SensorDeviceClass.TEMPERATURE
            )
        ),
        vol.Required(CONF_INDOOR_HUMIDITY): EntitySelector(
            EntitySelectorConfig(
                domain=Platform.SENSOR, device_class=SensorDeviceClass.HUMIDITY
            )
        ),
        vol.Required(CONF_OUTDOOR_TEMP): EntitySelector(
            EntitySelectorConfig(
                domain=Platform.SENSOR, device_class=SensorDeviceClass.TEMPERATURE
            )
        ),
    }
).extend(DATA_SCHEMA_OPTIONS.schema)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_CONFIG,
        validate_user_input=validate_input,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_input,
    )
}


class MoldIndicatorConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Mold indicator."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])

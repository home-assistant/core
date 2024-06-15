"""Config flow for Generic hygrostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from . import (
    CONF_AWAY_FIXED,
    CONF_AWAY_HUMIDITY,
    CONF_DEVICE_CLASS,
    CONF_DRY_TOLERANCE,
    CONF_HUMIDIFIER,
    CONF_INITIAL_STATE,
    CONF_KEEP_ALIVE,
    CONF_MAX_HUMIDITY,
    CONF_MIN_DUR,
    CONF_MIN_HUMIDITY,
    CONF_SENSOR,
    CONF_STALE_DURATION,
    CONF_WET_TOLERANCE,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

OPTIONS_SCHEMA = {
    vol.Required(CONF_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.HUMIDITY
        )
    ),
    vol.Required(CONF_HUMIDIFIER): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=SWITCH_DOMAIN)
    ),
    vol.Required(CONF_DEVICE_CLASS): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                HumidifierDeviceClass.HUMIDIFIER,
                HumidifierDeviceClass.DEHUMIDIFIER,
            ],
            translation_key=CONF_DEVICE_CLASS,
        ),
    ),
    vol.Required(
        CONF_DRY_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=0.5,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
    vol.Required(
        CONF_WET_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=0.5,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
    vol.Optional(CONF_INITIAL_STATE): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
    vol.Optional(CONF_MIN_DUR): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False)
    ),
    vol.Optional(CONF_MIN_HUMIDITY): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
    vol.Optional(CONF_MAX_HUMIDITY): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
    vol.Optional(CONF_AWAY_HUMIDITY): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=0.5,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
    vol.Optional(CONF_AWAY_FIXED): selector.BooleanSelector(),
    vol.Optional(CONF_KEEP_ALIVE): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False, enable_day=False)
    ),
    vol.Optional(CONF_STALE_DURATION): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False, enable_day=False)
    ),
}

CONFIG_SCHEMA = {
    vol.Required(CONF_NAME): selector.TextSelector(),
    **OPTIONS_SCHEMA,
}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(vol.Schema(CONFIG_SCHEMA)),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(vol.Schema(OPTIONS_SCHEMA)),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])

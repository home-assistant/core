"""Config flow for Generic hygrostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from . import (
    CONF_DEVICE_CLASS,
    CONF_DRY_TOLERANCE,
    CONF_HUMIDIFIER,
    CONF_KEEP_ALIVE,
    CONF_SENSOR,
    CONF_STALE_DURATION,
    CONF_WET_TOLERANCE,
    DEFAULT_TOLERANCE,
    DOMAIN,
)


async def _get_options_dict(handler: SchemaCommonFlowHandler | None) -> dict:
    return {
        vol.Required(CONF_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.HUMIDITY
            )
        ),
        vol.Required(CONF_HUMIDIFIER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SWITCH_DOMAIN)
        ),
        vol.Required(
            CONF_DRY_TOLERANCE, default=DEFAULT_TOLERANCE
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_WET_TOLERANCE, default=DEFAULT_TOLERANCE
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, mode=selector.NumberSelectorMode.BOX
            )
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
        vol.Optional(CONF_KEEP_ALIVE): selector.DurationSelector(
            selector.DurationSelectorConfig(allow_negative=False, enable_day=False)
        ),
        vol.Optional(CONF_STALE_DURATION): selector.DurationSelector(
            selector.DurationSelectorConfig(allow_negative=False, enable_day=False)
        ),
    }


async def _get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    return vol.Schema(await _get_options_dict(handler))


async def _get_config_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    options = await _get_options_dict(handler)
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            **options,
        },
    )


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(_get_config_schema),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(_get_options_schema),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])

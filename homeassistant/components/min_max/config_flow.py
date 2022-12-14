"""Config flow for Min/Max integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN
from .sensor import MinMaxSensor

_STATISTIC_MEASURES = [
    "min",
    "max",
    "mean",
    "median",
    "last",
    "range",
    "sum",
]


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_IDS): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=[SENSOR_DOMAIN, NUMBER_DOMAIN, INPUT_NUMBER_DOMAIN],
                multiple=True,
            ),
        ),
        vol.Required(CONF_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_STATISTIC_MEASURES, translation_key=CONF_TYPE
            ),
        ),
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=6, mode=selector.NumberSelectorMode.BOX
            ),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("name"): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, preview="min_max_preview"),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA, preview="min_max_preview"),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Min/Max."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""

    @callback
    @staticmethod
    def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        data_preview = f"{DOMAIN}_preview"
        if data_preview in hass.data:
            return
        websocket_api.async_register_command(hass, ws_preview_min_max)
        hass.data[data_preview] = None


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "min_max/preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
def ws_preview_min_max(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Generate a preview."""
    if msg["flow_type"] == "config_flow":
        validated = CONFIG_SCHEMA(msg["user_input"])
        name = validated["name"]
    else:
        validated = OPTIONS_SCHEMA(msg["user_input"])
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        if not config_entry:
            raise HomeAssistantError
        name = config_entry.options["name"]
    sensor = MinMaxSensor(
        validated[CONF_ENTITY_IDS],
        name,
        validated[CONF_TYPE],
        int(validated[CONF_ROUND_DIGITS]),
        None,
    )
    sensor.hass = hass
    state, attr = sensor.async_preview()

    connection.send_result(msg["id"], {"state": state, "attributes": attr})

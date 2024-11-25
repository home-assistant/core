"""Config flow for Mold indicator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
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
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
    DOMAIN,
)
from .sensor import MoldIndicator


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
        preview="mold_indicator",
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_input,
        preview="mold_indicator",
    )
}


class MoldIndicatorConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Mold indicator."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "mold_indicator/start_preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
@callback
def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a preview."""

    if msg["flow_type"] == "config_flow":
        flow_status = hass.config_entries.flow.async_get(msg["flow_id"])
        flow_sets = hass.config_entries.flow._handler_progress_index.get(  # noqa: SLF001
            flow_status["handler"]
        )
        assert flow_sets
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        indoor_temp = msg["user_input"].get(CONF_INDOOR_TEMP)
        outdoor_temp = msg["user_input"].get(CONF_OUTDOOR_TEMP)
        indoor_hum = msg["user_input"].get(CONF_INDOOR_HUMIDITY)
        name = msg["user_input"].get(CONF_NAME)
    else:
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        if not config_entry:
            raise HomeAssistantError("Config entry not found")
        indoor_temp = config_entry.options[CONF_INDOOR_TEMP]
        outdoor_temp = config_entry.options[CONF_OUTDOOR_TEMP]
        indoor_hum = config_entry.options[CONF_INDOOR_HUMIDITY]
        name = config_entry.options[CONF_NAME]

    @callback
    def async_preview_updated(state: str, attributes: Mapping[str, Any]) -> None:
        """Forward config entry state events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"], {"attributes": attributes, "state": state}
            )
        )

    preview_entity = MoldIndicator(
        hass,
        name,
        hass.config.units is METRIC_SYSTEM,
        indoor_temp,
        outdoor_temp,
        indoor_hum,
        msg["user_input"].get(CONF_CALIBRATION_FACTOR),
        None,
    )
    preview_entity.hass = hass

    connection.send_result(msg["id"])
    connection.subscriptions[msg["id"]] = preview_entity.async_start_preview(
        async_preview_updated
    )

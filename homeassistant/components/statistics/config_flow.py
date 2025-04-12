"""Config flow for statistics."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    DurationSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import DOMAIN
from .sensor import (
    CONF_KEEP_LAST_SAMPLE,
    CONF_MAX_AGE,
    CONF_PERCENTILE,
    CONF_PRECISION,
    CONF_SAMPLES_MAX_BUFFER_SIZE,
    CONF_STATE_CHARACTERISTIC,
    DEFAULT_NAME,
    DEFAULT_PRECISION,
    STATS_BINARY_SUPPORT,
    STATS_NUMERIC_SUPPORT,
    StatisticsSensor,
)


async def get_state_characteristics(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema with state characteristics."""
    is_binary = (
        split_entity_id(handler.options[CONF_ENTITY_ID])[0] == BINARY_SENSOR_DOMAIN
    )
    if is_binary:
        options = list(STATS_BINARY_SUPPORT)
    else:
        options = list(STATS_NUMERIC_SUPPORT)

    return vol.Schema(
        {
            vol.Required(CONF_STATE_CHARACTERISTIC): SelectSelector(
                SelectSelectorConfig(
                    options=list(options),
                    translation_key=CONF_STATE_CHARACTERISTIC,
                    sort=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""
    if (
        user_input.get(CONF_SAMPLES_MAX_BUFFER_SIZE) is None
        and user_input.get(CONF_MAX_AGE) is None
    ):
        raise SchemaFlowError("missing_max_age_or_sampling_size")

    if (
        user_input.get(CONF_KEEP_LAST_SAMPLE) is True
        and user_input.get(CONF_MAX_AGE) is None
    ):
        raise SchemaFlowError("missing_keep_last_sample")

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=[BINARY_SENSOR_DOMAIN, SENSOR_DOMAIN])
        ),
    }
)
DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_SAMPLES_MAX_BUFFER_SIZE): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAX_AGE): DurationSelector(
            DurationSelectorConfig(enable_day=False, allow_negative=False)
        ),
        vol.Optional(CONF_KEEP_LAST_SAMPLE, default=False): BooleanSelector(),
        vol.Optional(CONF_PERCENTILE, default=50): NumberSelector(
            NumberSelectorConfig(min=1, max=99, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SETUP,
        next_step="state_characteristic",
    ),
    "state_characteristic": SchemaFlowFormStep(
        schema=get_state_characteristics, next_step="options"
    ),
    "options": SchemaFlowFormStep(
        schema=DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_options,
        preview="statistics",
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_options,
        preview="statistics",
    ),
}


class StatisticsConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Statistics."""

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
        vol.Required("type"): "statistics/start_preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
@websocket_api.async_response
async def ws_start_preview(
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
        options = {}
        assert flow_sets
        for active_flow in flow_sets:
            options = active_flow._common_handler.options  # type: ignore [attr-defined] # noqa: SLF001
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        entity_id = options[CONF_ENTITY_ID]
        name = options[CONF_NAME]
        state_characteristic = options[CONF_STATE_CHARACTERISTIC]
    else:
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        if not config_entry:
            raise HomeAssistantError("Config entry not found")
        entity_id = config_entry.options[CONF_ENTITY_ID]
        name = config_entry.options[CONF_NAME]
        state_characteristic = config_entry.options[CONF_STATE_CHARACTERISTIC]

    @callback
    def async_preview_updated(state: str, attributes: Mapping[str, Any]) -> None:
        """Forward config entry state events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"], {"attributes": attributes, "state": state}
            )
        )

    sampling_size = msg["user_input"].get(CONF_SAMPLES_MAX_BUFFER_SIZE)
    if sampling_size:
        sampling_size = int(sampling_size)

    max_age = None
    if max_age_input := msg["user_input"].get(CONF_MAX_AGE):
        max_age = timedelta(
            hours=max_age_input["hours"],
            minutes=max_age_input["minutes"],
            seconds=max_age_input["seconds"],
        )
    preview_entity = StatisticsSensor(
        hass,
        entity_id,
        name,
        None,
        state_characteristic,
        sampling_size,
        max_age,
        msg["user_input"].get(CONF_KEEP_LAST_SAMPLE),
        msg["user_input"].get(CONF_PRECISION),
        msg["user_input"].get(CONF_PERCENTILE),
    )
    preview_entity.hass = hass

    connection.send_result(msg["id"])
    connection.subscriptions[msg["id"]] = await preview_entity.async_start_preview(
        async_preview_updated
    )

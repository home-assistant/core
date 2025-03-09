"""The history_stats component config flow."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_STATE, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    EntitySelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.helpers.template import Template

from .const import (
    CONF_DURATION,
    CONF_END,
    CONF_PERIOD_KEYS,
    CONF_START,
    CONF_TYPE_KEYS,
    CONF_TYPE_TIME,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import HistoryStatsUpdateCoordinator
from .data import HistoryStats
from .sensor import HistoryStatsSensor


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""
    if sum(param in user_input for param in CONF_PERIOD_KEYS) != 2:
        raise SchemaFlowError("only_two_keys_allowed")

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ENTITY_ID): EntitySelector(),
        vol.Required(CONF_STATE): TextSelector(TextSelectorConfig(multiple=True)),
        vol.Required(CONF_TYPE, default=CONF_TYPE_TIME): SelectSelector(
            SelectSelectorConfig(
                options=CONF_TYPE_KEYS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_TYPE,
            )
        ),
    }
)
DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_START): TemplateSelector(),
        vol.Optional(CONF_END): TemplateSelector(),
        vol.Optional(CONF_DURATION): DurationSelector(
            DurationSelectorConfig(enable_day=True, allow_negative=False)
        ),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SETUP,
        next_step="options",
    ),
    "options": SchemaFlowFormStep(
        schema=DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_options,
        preview="history_stats",
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_options,
        preview="history_stats",
    ),
}


class StatisticsConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for History stats."""

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
        vol.Required("type"): "history_stats/start_preview",
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
        sensor_type = options[CONF_TYPE]
    else:
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        if not config_entry:
            raise HomeAssistantError("Config entry not found")
        entity_id = config_entry.options[CONF_ENTITY_ID]
        name = config_entry.options[CONF_NAME]
        sensor_type = config_entry.options[CONF_TYPE]

    @callback
    def async_preview_updated(state: str, attributes: Mapping[str, Any]) -> None:
        """Forward config entry state events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"], {"attributes": attributes, "state": state}
            )
        )

    entity_id = options[CONF_ENTITY_ID]
    entity_states: list[str] = options[CONF_STATE]
    start: str | None = options.get(CONF_START)
    end: str | None = options.get(CONF_END)
    duration: timedelta | None = None
    if duration_dict := options.get(CONF_DURATION):
        duration = timedelta(**duration_dict)

    if sum(param in options for param in CONF_PERIOD_KEYS) != 2:
        return

    history_stats = HistoryStats(
        hass,
        entity_id,
        entity_states,
        Template(start, hass) if start else None,
        Template(end, hass) if end else None,
        duration,
    )
    coordinator = HistoryStatsUpdateCoordinator(hass, history_stats, None, name)
    await coordinator.async_refresh()

    preview_entity = HistoryStatsSensor(
        hass, coordinator, sensor_type, name, None, entity_id
    )
    preview_entity.hass = hass

    connection.send_result(msg["id"])
    connection.subscriptions[msg["id"]] = await preview_entity.async_start_preview(
        async_preview_updated
    )

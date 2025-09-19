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
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    StateSelector,
    StateSelectorConfig,
    TemplateSelector,
    TextSelector,
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


def _validate_two_period_keys(user_input: dict[str, Any]) -> None:
    if sum(param in user_input for param in CONF_PERIOD_KEYS) != 2:
        raise SchemaFlowError("only_two_keys_allowed")


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""
    _validate_two_period_keys(user_input)

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ENTITY_ID): EntitySelector(),
        vol.Required(CONF_TYPE, default=CONF_TYPE_TIME): SelectSelector(
            SelectSelectorConfig(
                options=CONF_TYPE_KEYS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_TYPE,
            )
        ),
    }
)


async def get_state_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for state step."""
    entity_id = handler.options[CONF_ENTITY_ID]

    return vol.Schema(
        {
            vol.Optional(CONF_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(read_only=True)
            ),
            vol.Required(CONF_STATE): StateSelector(
                StateSelectorConfig(
                    multiple=True,
                    entity_id=entity_id,
                )
            ),
        }
    )


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for options step."""
    entity_id = handler.options[CONF_ENTITY_ID]
    return _get_options_schema_with_entity_id(entity_id)


def _get_options_schema_with_entity_id(entity_id: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(read_only=True)
            ),
            vol.Optional(CONF_STATE): StateSelector(
                StateSelectorConfig(
                    multiple=True,
                    entity_id=entity_id,
                    read_only=True,
                )
            ),
            vol.Optional(CONF_TYPE): SelectSelector(
                SelectSelectorConfig(
                    options=CONF_TYPE_KEYS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_TYPE,
                    read_only=True,
                )
            ),
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
        next_step="state",
    ),
    "state": SchemaFlowFormStep(schema=get_state_schema, next_step="options"),
    "options": SchemaFlowFormStep(
        schema=get_options_schema,
        validate_user_input=validate_options,
        preview="history_stats",
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        schema=get_options_schema,
        validate_user_input=validate_options,
        preview="history_stats",
    ),
}


class HistoryStatsConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for History stats."""

    MINOR_VERSION = 2

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
    else:
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        if not config_entry:
            raise HomeAssistantError("Config entry not found")
        entity_id = config_entry.options[CONF_ENTITY_ID]
        name = config_entry.options[CONF_NAME]

    @callback
    def async_preview_updated(
        last_exception: Exception | None, state: str, attributes: Mapping[str, Any]
    ) -> None:
        """Forward config entry state events to websocket."""
        if last_exception:
            connection.send_message(
                websocket_api.event_message(
                    msg["id"], {"error": str(last_exception) or "Unknown error"}
                )
            )
        else:
            connection.send_message(
                websocket_api.event_message(
                    msg["id"], {"attributes": attributes, "state": state}
                )
            )

    for param in CONF_PERIOD_KEYS:
        if param in msg["user_input"] and not bool(msg["user_input"][param]):
            del msg["user_input"][param]  # Remove falsy values before counting keys

    validated_data: Any = None
    try:
        validated_data = (_get_options_schema_with_entity_id(entity_id))(
            msg["user_input"]
        )
    except vol.Invalid as ex:
        connection.send_error(msg["id"], "invalid_schema", str(ex))
        return

    try:
        _validate_two_period_keys(validated_data)
    except SchemaFlowError:
        connection.send_error(
            msg["id"],
            "invalid_schema",
            f"Exactly two of {', '.join(CONF_PERIOD_KEYS)} required",
        )
        return

    sensor_type = validated_data.get(CONF_TYPE)
    entity_states = validated_data.get(CONF_STATE)
    start = validated_data.get(CONF_START)
    end = validated_data.get(CONF_END)
    duration = validated_data.get(CONF_DURATION)

    history_stats = HistoryStats(
        hass,
        entity_id,
        entity_states,
        Template(start, hass) if start else None,
        Template(end, hass) if end else None,
        timedelta(**duration) if duration else None,
        True,
    )
    coordinator = HistoryStatsUpdateCoordinator(hass, history_stats, None, name, True)
    await coordinator.async_refresh()
    preview_entity = HistoryStatsSensor(
        hass,
        coordinator=coordinator,
        sensor_type=sensor_type,
        name=name,
        unique_id=None,
        source_entity_id=entity_id,
    )
    preview_entity.hass = hass

    connection.send_result(msg["id"])
    cancel_listener = coordinator.async_setup_state_listener()
    cancel_preview = await preview_entity.async_start_preview(async_preview_updated)

    def unsub() -> None:
        cancel_listener()
        cancel_preview()

    connection.subscriptions[msg["id"]] = unsub

"""Config flow for Group integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from functools import partial
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITIES, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
    entity_selector_without_own_entities,
)

from . import DOMAIN
from .binary_sensor import CONF_ALL
from .const import CONF_HIDE_MEMBERS, CONF_IGNORE_NON_NUMERIC
from .sensor import SensorGroup

_STATISTIC_MEASURES = [
    "min",
    "max",
    "mean",
    "median",
    "last",
    "range",
    "sum",
    "product",
]


async def basic_group_options_schema(
    domain: str | list[str], handler: SchemaCommonFlowHandler | None
) -> vol.Schema:
    """Generate options schema."""
    if handler is None:
        entity_selector = selector.selector(
            {"entity": {"domain": domain, "multiple": True}}
        )
    else:
        entity_selector = entity_selector_without_own_entities(
            cast(SchemaOptionsFlowHandler, handler.parent_handler),
            selector.EntitySelectorConfig(domain=domain, multiple=True),
        )

    return vol.Schema(
        {
            vol.Required(CONF_ENTITIES): entity_selector,
            vol.Required(CONF_HIDE_MEMBERS, default=False): selector.BooleanSelector(),
        }
    )


def basic_group_config_schema(domain: str | list[str]) -> vol.Schema:
    """Generate config schema."""
    return vol.Schema(
        {
            vol.Required("name"): selector.TextSelector(),
            vol.Required(CONF_ENTITIES): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=domain, multiple=True),
            ),
            vol.Required(CONF_HIDE_MEMBERS, default=False): selector.BooleanSelector(),
        }
    )


async def binary_sensor_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Generate options schema."""
    return (await basic_group_options_schema("binary_sensor", handler)).extend(
        {
            vol.Required(CONF_ALL, default=False): selector.BooleanSelector(),
        }
    )


BINARY_SENSOR_CONFIG_SCHEMA = basic_group_config_schema("binary_sensor").extend(
    {
        vol.Required(CONF_ALL, default=False): selector.BooleanSelector(),
    }
)

SENSOR_CONFIG_EXTENDS = {
    vol.Required(CONF_TYPE): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_STATISTIC_MEASURES, translation_key=CONF_TYPE
        ),
    ),
}
SENSOR_OPTIONS = {
    vol.Optional(CONF_IGNORE_NON_NUMERIC, default=False): selector.BooleanSelector(),
    vol.Required(CONF_TYPE): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_STATISTIC_MEASURES, translation_key=CONF_TYPE
        ),
    ),
}


async def sensor_options_schema(
    domain: str, handler: SchemaCommonFlowHandler | None
) -> vol.Schema:
    """Generate options schema."""
    return (
        await basic_group_options_schema(["sensor", "number", "input_number"], handler)
    ).extend(SENSOR_OPTIONS)


SENSOR_CONFIG_SCHEMA = basic_group_config_schema(
    ["sensor", "number", "input_number"]
).extend(SENSOR_CONFIG_EXTENDS)


async def light_switch_options_schema(
    domain: str, handler: SchemaCommonFlowHandler
) -> vol.Schema:
    """Generate options schema."""
    return (await basic_group_options_schema(domain, handler)).extend(
        {
            vol.Required(
                CONF_ALL, default=False, description={"advanced": True}
            ): selector.BooleanSelector(),
        }
    )


GROUP_TYPES = [
    "binary_sensor",
    "cover",
    "fan",
    "light",
    "lock",
    "media_player",
    "sensor",
    "switch",
]


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to group_type."""
    return cast(str, options["group_type"])


def set_group_type(
    group_type: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]
]:
    """Set group type."""

    async def _set_group_type(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Add group type to user input."""
        return {"group_type": group_type, **user_input}

    return _set_group_type


CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(GROUP_TYPES),
    "binary_sensor": SchemaFlowFormStep(
        BINARY_SENSOR_CONFIG_SCHEMA,
        validate_user_input=set_group_type("binary_sensor"),
    ),
    "cover": SchemaFlowFormStep(
        basic_group_config_schema("cover"),
        validate_user_input=set_group_type("cover"),
    ),
    "fan": SchemaFlowFormStep(
        basic_group_config_schema("fan"),
        validate_user_input=set_group_type("fan"),
    ),
    "light": SchemaFlowFormStep(
        basic_group_config_schema("light"),
        validate_user_input=set_group_type("light"),
    ),
    "lock": SchemaFlowFormStep(
        basic_group_config_schema("lock"),
        validate_user_input=set_group_type("lock"),
    ),
    "media_player": SchemaFlowFormStep(
        basic_group_config_schema("media_player"),
        validate_user_input=set_group_type("media_player"),
    ),
    "sensor": SchemaFlowFormStep(
        SENSOR_CONFIG_SCHEMA,
        validate_user_input=set_group_type("sensor"),
        preview="group_sensor",
    ),
    "switch": SchemaFlowFormStep(
        basic_group_config_schema("switch"),
        validate_user_input=set_group_type("switch"),
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    "binary_sensor": SchemaFlowFormStep(binary_sensor_options_schema),
    "cover": SchemaFlowFormStep(partial(basic_group_options_schema, "cover")),
    "fan": SchemaFlowFormStep(partial(basic_group_options_schema, "fan")),
    "light": SchemaFlowFormStep(partial(light_switch_options_schema, "light")),
    "lock": SchemaFlowFormStep(partial(basic_group_options_schema, "lock")),
    "media_player": SchemaFlowFormStep(
        partial(basic_group_options_schema, "media_player")
    ),
    "sensor": SchemaFlowFormStep(
        partial(sensor_options_schema, "sensor"),
        preview="group_sensor",
    ),
    "switch": SchemaFlowFormStep(partial(light_switch_options_schema, "switch")),
}


class GroupConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for groups."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title.

        The options parameter contains config entry options, which is the union of user
        input from the config flow steps.
        """
        return cast(str, options["name"]) if "name" in options else ""

    @callback
    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Hide the group members if requested."""
        if options[CONF_HIDE_MEMBERS]:
            _async_hide_members(
                self.hass, options[CONF_ENTITIES], er.RegistryEntryHider.INTEGRATION
            )

    @callback
    @staticmethod
    def async_options_flow_finished(
        hass: HomeAssistant, options: Mapping[str, Any]
    ) -> None:
        """Hide or unhide the group members as requested."""
        hidden_by = (
            er.RegistryEntryHider.INTEGRATION if options[CONF_HIDE_MEMBERS] else None
        )
        _async_hide_members(hass, options[CONF_ENTITIES], hidden_by)

    @callback
    @staticmethod
    def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_preview_sensor)


def _async_hide_members(
    hass: HomeAssistant, members: list[str], hidden_by: er.RegistryEntryHider | None
) -> None:
    """Hide or unhide group members."""
    registry = er.async_get(hass)
    for member in members:
        if not (entity_id := er.async_resolve_entity_id(registry, member)):
            continue
        if entity_id not in registry.entities:
            continue
        registry.async_update_entity(entity_id, hidden_by=hidden_by)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "group/sensor/preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
@websocket_api.async_response
async def ws_preview_sensor(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Generate a preview."""
    if msg["flow_type"] == "config_flow":
        validated = SENSOR_CONFIG_SCHEMA(msg["user_input"])
        ignore_non_numeric = False
        name = validated["name"]
    else:
        validated = (await sensor_options_schema("sensor", None))(msg["user_input"])
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        config_entry = hass.config_entries.async_get_entry(flow_status["handler"])
        if not config_entry:
            raise HomeAssistantError
        ignore_non_numeric = validated[CONF_IGNORE_NON_NUMERIC]
        name = config_entry.options["name"]
    sensor = SensorGroup(
        None,
        name,
        validated[CONF_ENTITIES],
        ignore_non_numeric,
        validated[CONF_TYPE],
        None,
        None,
        None,
    )
    sensor.hass = hass
    state, attr = sensor.async_preview()

    connection.send_result(msg["id"], {"state": state, "attributes": attr})

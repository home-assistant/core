"""Config flow for Group integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowFormStep,
    HelperFlowMenuStep,
)

from . import DOMAIN
from .binary_sensor import CONF_ALL
from .const import CONF_HIDE_MEMBERS


def basic_group_options_schema(domain: str) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(
        {
            vol.Required(CONF_ENTITIES): selector.selector(
                {"entity": {"domain": domain, "multiple": True}}
            ),
            vol.Required(CONF_HIDE_MEMBERS, default=False): selector.selector(
                {"boolean": {}}
            ),
        }
    )


def basic_group_config_schema(domain: str) -> vol.Schema:
    """Generate config schema."""
    return vol.Schema({vol.Required("name"): selector.selector({"text": {}})}).extend(
        basic_group_options_schema(domain).schema
    )


BINARY_SENSOR_OPTIONS_SCHEMA = basic_group_options_schema("binary_sensor").extend(
    {
        vol.Required(CONF_ALL, default=False): selector.selector({"boolean": {}}),
    }
)

LIGHT_OPTIONS_SCHEMA = basic_group_options_schema("light").extend(
    {
        vol.Required(
            CONF_ALL, default=False, description={"advanced": True}
        ): selector.selector({"boolean": {}}),
    }
)

BINARY_SENSOR_CONFIG_SCHEMA = vol.Schema(
    {vol.Required("name"): selector.selector({"text": {}})}
).extend(BINARY_SENSOR_OPTIONS_SCHEMA.schema)

GROUP_TYPES = ["binary_sensor", "cover", "fan", "light", "media_player"]


@callback
def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to group_type."""
    return cast(str, options["group_type"])


def set_group_type(group_type: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Set group type."""

    @callback
    def _set_group_type(user_input: dict[str, Any]) -> dict[str, Any]:
        """Add group type to user input."""
        return {"group_type": group_type, **user_input}

    return _set_group_type


CONFIG_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "user": HelperFlowMenuStep(GROUP_TYPES),
    "binary_sensor": HelperFlowFormStep(
        BINARY_SENSOR_CONFIG_SCHEMA, set_group_type("binary_sensor")
    ),
    "cover": HelperFlowFormStep(
        basic_group_config_schema("cover"), set_group_type("cover")
    ),
    "fan": HelperFlowFormStep(basic_group_config_schema("fan"), set_group_type("fan")),
    "light": HelperFlowFormStep(
        basic_group_config_schema("light"), set_group_type("light")
    ),
    "media_player": HelperFlowFormStep(
        basic_group_config_schema("media_player"), set_group_type("media_player")
    ),
}


OPTIONS_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "init": HelperFlowFormStep(None, next_step=choose_options_step),
    "binary_sensor": HelperFlowFormStep(BINARY_SENSOR_OPTIONS_SCHEMA),
    "cover": HelperFlowFormStep(basic_group_options_schema("cover")),
    "fan": HelperFlowFormStep(basic_group_options_schema("fan")),
    "light": HelperFlowFormStep(LIGHT_OPTIONS_SCHEMA),
    "media_player": HelperFlowFormStep(basic_group_options_schema("media_player")),
}


class GroupConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Switch Light."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
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

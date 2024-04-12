"""Module to coordinate llm tools."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable
import json
import logging
from typing import Any

import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED, convert

from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.util import dt as dt_util

from . import (
    area_registry as ar,
    config_validation as cv,
    entity_registry as er,
    intent,
    template,
)

_LOGGER = logging.getLogger(__name__)

DATA_KEY = "llm_tool"


class Tool:
    """LLM Tool base class."""

    name: str
    description: str
    parameters: dict[str, Any]

    @property
    def specification(self) -> dict[str, Any]:
        """Get the tool specification."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def __init__(self, name: str, description: str, parameters: dict[str, Any]) -> None:
        """Init the class."""
        self.name = name
        self.description = description
        self.parameters = parameters

    @abstractmethod
    async def async_call(
        self,
        hass: HomeAssistant,
        platform: str,
        text_input: str | None,
        context: Context,
        language: str | None,
        assistant: str | None,
        **kwargs: Any,
    ) -> Any:
        """Call the tool."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """Represent a string of a Tool."""
        return f"<{self.__class__.__name__} - {self.name}>"


@callback
def async_register_tool(hass: HomeAssistant, tool: Tool) -> None:
    """Register an LLM tool with Home Assistant."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = hass.data[DATA_KEY] = {}

    assert tool.specification is not None, "tool specification cannot be None"

    if tool.name in tools:
        _LOGGER.warning("Tool %s is being overwritten by %s", tool.name, tool)

    tools[tool.name] = tool


@callback
def async_remove_tool(hass: HomeAssistant, tool_name: str) -> None:
    """Remove an LLM tool from Home Assistant."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        return

    tools.pop(tool_name, None)


@callback
def async_get_tools(hass: HomeAssistant) -> Iterable[Tool]:
    """Return a list of registered LLM tools."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = {}

    return tools.values()


@callback
async def async_call_tool(
    hass: HomeAssistant,
    platform: str,
    tool_name: str,
    json_args: str = "{}",
    text_input: str | None = None,
    context: Context | None = None,
    language: str | None = None,
    assistant: str | None = None,
) -> str:
    """Call a LLM tool, parse args and return the response."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = {}

    if context is None:
        context = Context()

    try:
        tool = tools[tool_name]
        tool_args = json.loads(json_args)
        response = await tool.async_call(
            hass, platform, text_input, context, language, assistant, **tool_args
        )
        json_response = json.dumps(response)

    except Exception as e:  # pylint: disable=broad-exception-caught
        response = {"error": type(e).__name__}
        if str(e):
            response["error_text"] = str(e)
        json_response = json.dumps(response)

    return json_response


EXPORTED_ATTRIBUTES = [
    "device_class",
    "message",
    "all_day",
    "start_time",
    "end_time",
    "location",
    "description",
    "hvac_modes",
    "min_temp",
    "max_temp",
    "fan_modes",
    "preset_modes",
    "swing_modes",
    "current_temperature",
    "temperature",
    "target_temp_high",
    "target_temp_low",
    "fan_mode",
    "preset_mode",
    "swing_mode",
    "hvac_action",
    "aux_heat",
    "current_position",
    "current_tilt_position",
    "latitude",
    "longitude",
    "percentage",
    "direction",
    "oscillating",
    "available_modes",
    "max_humidity",
    "min_humidity",
    "action",
    "current_humidity",
    "humidity",
    "mode",
    "faces",
    "total_faces",
    "min",
    "max",
    "step",
    "min_color_temp_kelvin",
    "max_color_temp_kelvin",
    "min_mireds",
    "max_mireds",
    "effect_list",
    "supported_color_modes",
    "color_mode",
    "brightness",
    "color_temp_kelvin",
    "color_temp",
    "hs_color",
    "rgb_color",
    "xy_color",
    "rgbw_color",
    "rgbww_color",
    "effect",
    "sound_mode_list",
    "volume_level",
    "is_volume_muted",
    "media_content_type",
    "media_duration",
    "media_position",
    "media_title",
    "media_artist",
    "media_album_name",
    "media_track",
    "media_series_title",
    "media_season",
    "media_episode",
    "app_name",
    "sound_mode",
    "shuffle",
    "repeat",
    "source",
    "options",
    "battery_level",
    "available_tones",
    "elevation",
    "rising",
    "fan_speed_list",
    "fan_speed",
    "status",
    "cleaned_area",
    "operation_list",
    "operation_mode",
    "away_mode",
    "temperature_unit",
    "pressure",
    "pressure_unit",
    "wind_speed",
    "wind_speed_unit",
    "dew_point",
    "cloud_coverage",
    "persons",
]


def _format_state(hass: HomeAssistant, entity_state: State) -> dict[str, Any]:
    """Format state for better understanding by a LLM."""
    entity_registry = er.async_get(hass)
    entity_state = template.TemplateState(hass, entity_state, collect=False)

    result: dict[str, Any] = {
        "name": entity_state.name,
        "entity_id": entity_state.entity_id,
        "state": entity_state.state_with_unit,
        "last_changed": dt_util.get_age(entity_state.last_changed) + " ago",
    }

    if registry_entry := entity_registry.async_get(entity_state.entity_id):
        if area_name := template.area_name(hass, entity_state.entity_id):
            result["area"] = area_name
        if len(registry_entry.aliases):
            result["aliases"] = list(registry_entry.aliases)

    attributes: dict[str, Any] = {}
    for attribute, value in entity_state.attributes.items():
        if attribute in EXPORTED_ATTRIBUTES:
            attributes[attribute] = value
    if attributes:
        result["attributes"] = attributes

    return result


def custom_serializer(schema: Any) -> Any:
    """Serialize additional types in OpenAPI-compatible format."""
    from homeassistant.util.color import (  # pylint: disable=import-outside-toplevel
        color_name_to_rgb,
    )

    if schema is cv.string:
        return {"type": "string"}

    if schema is cv.boolean:
        return {"type": "boolean"}

    if schema is cv.ensure_list:
        return {}

    if schema is color_name_to_rgb:
        return {"type": "string"}

    if isinstance(schema, cv.multi_select):
        return {"enum": schema.options}

    return UNSUPPORTED


class IntentTool(Tool):
    """LLM Tool representing an Intent."""

    def __init__(self, intent_type: str, slot_schema: vol.Schema | None = None) -> None:
        """Init the class."""
        if slot_schema is None:
            slot_schema = vol.Schema({})
        super().__init__(
            intent_type,
            f"Execute Home Assistant {intent_type} intent",
            convert(slot_schema, custom_serializer=custom_serializer),
        )

    async def async_call(
        self,
        hass: HomeAssistant,
        platform: str,
        text_input: str | None,
        context: Context,
        language: str | None,
        assistant: str | None,
        **kwargs: Any,
    ) -> Any:
        """Handle the intent."""
        slots = {key: {"value": val} for key, val in kwargs.items()}

        if "area" in slots:
            areas = ar.async_get(hass)
            id_or_name = slots["area"]["value"]

            area = areas.async_get_area(id_or_name) or areas.async_get_area_by_name(
                id_or_name
            )
            if not area:
                # Check area aliases
                for maybe_area in areas.areas.values():
                    if not maybe_area.aliases:
                        continue

                    for area_alias in maybe_area.aliases:
                        if id_or_name == area_alias.casefold():
                            return maybe_area
            if area:
                slots["area"]["value"] = area.id
                slots["area"]["text"] = area.name
            else:
                slots["area"]["text"] = id_or_name

        intent_response = await intent.async_handle(
            hass, platform, self.name, slots, text_input, context, language, assistant
        )
        response = intent_response.as_dict()
        if intent_response.matched_states:
            response["data"]["matched_states"] = [
                _format_state(hass, state) for state in intent_response.matched_states
            ]
        if intent_response.unmatched_states:
            response["data"]["unmatched_states"] = [
                _format_state(hass, state) for state in intent_response.unmatched_states
            ]
        return response

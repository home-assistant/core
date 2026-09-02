"""Config flow for Times of the Day integration."""

from collections.abc import Mapping
from typing import Any, cast, override

import voluptuous as vol

from homeassistant.const import (
    CONF_AFTER,
    CONF_BEFORE,
    CONF_NAME,
    CONF_OFFSET,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import (
    CONF_AFTER_OFFSET,
    CONF_AFTER_TIME,
    CONF_BEFORE_OFFSET,
    CONF_BEFORE_TIME,
    DOMAIN,
    MAX_OFFSET,
)

CONF_SUN_EVENT = "sun_event"
CONF_TIME = "time"

SUN_EVENT_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET],
        mode=selector.SelectSelectorMode.DROPDOWN,
        translation_key="sun_event",
    )
)

OFFSET_SELECTOR = selector.DurationSelector(
    selector.DurationSelectorConfig(allow_negative=True)
)


def _boundary_section(boundary_schema: vol.Schema) -> section:
    """Return an expanded boundary section."""
    return section(boundary_schema, SectionConfig(collapsed=False))


BOUNDARY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TIME): selector.TimeSelector(),
        vol.Optional(CONF_SUN_EVENT): SUN_EVENT_SELECTOR,
        vol.Optional(CONF_OFFSET): OFFSET_SELECTOR,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_AFTER): _boundary_section(BOUNDARY_SCHEMA),
        vol.Required(CONF_BEFORE): _boundary_section(BOUNDARY_SCHEMA),
    }
)


def _resolve_sections(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Flatten the boundary sections into stored options."""
    resolved_input = {
        key: value
        for key, value in user_input.items()
        if key not in (CONF_AFTER, CONF_BEFORE)
    }
    omitted_offsets: list[str] = []
    for section_key, time_key, offset_key in (
        (CONF_AFTER, CONF_AFTER_TIME, CONF_AFTER_OFFSET),
        (CONF_BEFORE, CONF_BEFORE_TIME, CONF_BEFORE_OFFSET),
    ):
        section_input = user_input[section_key]
        time_value = section_input.get(CONF_TIME)
        sun_event = section_input.get(CONF_SUN_EVENT)
        if (time_value is None) == (sun_event is None):
            raise SchemaFlowError(f"{section_key}_one_value")
        resolved_input[time_key] = time_value or sun_event
        if CONF_OFFSET in section_input:
            if abs(cv.time_period(section_input[CONF_OFFSET])) > MAX_OFFSET:
                raise SchemaFlowError(f"{section_key}_offset_range")
            resolved_input[offset_key] = section_input[CONF_OFFSET]
        else:
            omitted_offsets.append(offset_key)
    for offset_key in omitted_offsets:
        handler.options.pop(offset_key, None)
    return resolved_input


async def _validate_sections(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate and resolve the boundary sections."""
    return _resolve_sections(handler, user_input)


def _options_boundary_schema(value: str) -> vol.Schema:
    """Return an options section preserving the stored boundary type."""
    value_schema: dict[vol.Marker, selector.Selector] = {}
    if value in (SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET):
        value_schema[vol.Required(CONF_SUN_EVENT)] = SUN_EVENT_SELECTOR
    else:
        value_schema[vol.Required(CONF_TIME)] = selector.TimeSelector()
    value_schema[vol.Optional(CONF_OFFSET)] = OFFSET_SELECTOR
    return vol.Schema(value_schema)


async def _options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return an options schema preserving each stored boundary type."""
    return vol.Schema(
        {
            vol.Required(CONF_AFTER): _boundary_section(
                _options_boundary_schema(handler.options[CONF_AFTER_TIME])
            ),
            vol.Required(CONF_BEFORE): _boundary_section(
                _options_boundary_schema(handler.options[CONF_BEFORE_TIME])
            ),
        }
    )


async def _options_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Nest stored options for the section schema."""
    suggested_values: dict[str, Any] = {}
    for section_key, time_key, offset_key in (
        (CONF_AFTER, CONF_AFTER_TIME, CONF_AFTER_OFFSET),
        (CONF_BEFORE, CONF_BEFORE_TIME, CONF_BEFORE_OFFSET),
    ):
        value = handler.options[time_key]
        section_values = {
            CONF_SUN_EVENT
            if value in (SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET)
            else CONF_TIME: value
        }
        if offset_key in handler.options:
            section_values[CONF_OFFSET] = handler.options[offset_key]
        suggested_values[section_key] = section_values
    return suggested_values


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        CONFIG_SCHEMA,
        validate_user_input=_validate_sections,
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        _options_schema,
        validate_user_input=_validate_sections,
        suggested_values=_options_suggested_values,
    ),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Times of the Day."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])

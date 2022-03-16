"""Config flow for Threshold integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowError,
    HelperFlowStep,
    wrapped_entity_config_entry_title,
)

from .const import (
    CONF_HYSTERESIS,
    CONF_LOWER,
    CONF_UPPER,
    DEFAULT_HYSTERESIS,
    DOMAIN,
    TYPE_LOWER,
    TYPE_RANGE,
    TYPE_UPPER,
)

_THRESHOLD_MODES = [TYPE_LOWER, TYPE_UPPER, TYPE_RANGE]


def _validate_mode(data: Any) -> Any:
    """Validate the threshold mode."""
    if data["mode"] == TYPE_LOWER:
        try:
            vol.Schema(float)(data[CONF_LOWER])
            data[CONF_UPPER] = None
        except vol.Invalid as exc:
            raise HelperFlowError("lower_needs_lower") from exc
        return data
    if data["mode"] == TYPE_UPPER:
        try:
            vol.Schema(float)(data[CONF_UPPER])
            data[CONF_LOWER] = None
        except vol.Invalid as exc:
            raise HelperFlowError("upper_needs_upper") from exc
        return data
    try:
        vol.Schema(float)(data[CONF_LOWER])
        vol.Schema(float)(data[CONF_UPPER])
    except vol.Invalid as exc:
        raise HelperFlowError("range_needs_lower_upper") from exc
    return data


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("mode"): selector.selector(
            {"select": {"options": _THRESHOLD_MODES}}
        ),
        vol.Required(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): selector.selector(
            {"number": {"mode": "box"}}
        ),
        vol.Required(CONF_LOWER, default=None): vol.Any(
            None, selector.selector({"number": {"mode": "box"}})
        ),
        vol.Required(CONF_UPPER, default=None): vol.Any(
            None, selector.selector({"number": {"mode": "box"}})
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.selector(
            {"entity": {"domain": "sensor"}}
        ),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": HelperFlowStep(CONFIG_SCHEMA, validate_user_input=_validate_mode)
}

OPTIONS_FLOW = {
    "init": HelperFlowStep(OPTIONS_SCHEMA, validate_user_input=_validate_mode)
}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Threshold."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return (
            wrapped_entity_config_entry_title(self.hass, options[CONF_ENTITY_ID])
            + " threshold"
        )

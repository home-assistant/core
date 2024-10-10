"""Helpers to configure automation-like objects."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_ACTION,
    CONF_ACTIONS,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_TRIGGER,
    CONF_TRIGGERS,
)


def backward_compatibility_schema(value: Any | None) -> Any:
    """Backward compatibility for trigger/condition/action definitions."""

    if not isinstance(value, dict):
        return value

    # `trigger` has been renamed to `triggers`
    if CONF_TRIGGER in value:
        if CONF_TRIGGERS in value:
            raise vol.Invalid(
                "Cannot specify both 'trigger' and 'triggers'. Please use 'triggers' only."
            )
        value[CONF_TRIGGERS] = value.pop(CONF_TRIGGER)

    # `condition` has been renamed to `conditions`
    if CONF_CONDITION in value:
        if CONF_CONDITIONS in value:
            raise vol.Invalid(
                "Cannot specify both 'condition' and 'conditions'. Please use 'conditions' only."
            )
        value[CONF_CONDITIONS] = value.pop(CONF_CONDITION)

    # `action` has been renamed to `actions`
    if CONF_ACTION in value:
        if CONF_ACTIONS in value:
            raise vol.Invalid(
                "Cannot specify both 'action' and 'actions'. Please use 'actions' only."
            )
        value[CONF_ACTIONS] = value.pop(CONF_ACTION)

    return value

"""Config flow for Min/Max integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Literal, cast

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    CONF_PERIOD,
    CONF_PRECISION,
    CONF_STATE_CHARACTERISTIC,
    DOMAIN,
    STAT_AVERAGE_STEP_LTS,
    STAT_SUM_DIFFERENCES_LTS,
    STAT_VALUE_MAX_LTS,
    STAT_VALUE_MIN_LTS,
)

_CALENDAR_PERIODS = [
    selector.SelectOptionDict(value="hour", label="Hour"),
    selector.SelectOptionDict(value="day", label="Day"),
    selector.SelectOptionDict(value="week", label="Week"),
    selector.SelectOptionDict(value="month", label="Month"),
    selector.SelectOptionDict(value="year", label="Year"),
]

_STATISTIC_CHARACTERISTICS = [
    selector.SelectOptionDict(value=STAT_VALUE_MIN_LTS, label="Minimum"),
    selector.SelectOptionDict(value=STAT_VALUE_MAX_LTS, label="Maximum"),
    selector.SelectOptionDict(value=STAT_AVERAGE_STEP_LTS, label="Arithmetic mean"),
    selector.SelectOptionDict(
        value=STAT_SUM_DIFFERENCES_LTS, label="Sum of differences (change)"
    ),
]

PERIOD_TYPES = [
    "calendar",
    "fixed_period",
    "rolling_window",
]

OPTIONS_SCHEMA_STEP_1 = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SENSOR_DOMAIN),
        ),
        vol.Required(CONF_STATE_CHARACTERISTIC): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_STATISTIC_CHARACTERISTICS),
        ),
        vol.Required(CONF_PRECISION, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=6, mode=selector.NumberSelectorMode.BOX
            ),
        ),
    }
)

CONFIG_SCHEMA_STEP_1 = vol.Schema(
    {
        vol.Required("name"): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA_STEP_1.schema)

CALENDAR_PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required("calendar_period"): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_CALENDAR_PERIODS),
        ),
        vol.Required("calendar_offset", default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, mode=selector.NumberSelectorMode.BOX),
        ),
    }
)

FIXED_PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required("fixed_period_start_time"): selector.DateTimeSelector(),
        vol.Required("fixed_period_end_time"): selector.DateTimeSelector(),
    }
)

ROLLING_WINDOW_PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required("rolling_window_duration"): selector.DurationSelector(
            selector.DurationSelectorConfig(enable_day=True)
        ),
        vol.Required("rolling_window_offset"): selector.DurationSelector(
            selector.DurationSelectorConfig(enable_day=True)
        ),
    }
)

RECORDER_CHARACTERISTIC_TO_STATS_LTS: dict[
    Literal["max", "mean", "min", "change"], str
] = {
    "change": STAT_SUM_DIFFERENCES_LTS,
    "max": STAT_VALUE_MAX_LTS,
    "mean": STAT_AVERAGE_STEP_LTS,
    "min": STAT_VALUE_MIN_LTS,
}


@callback
def _import_or_user_config(options: dict[str, Any]) -> str | None:
    """Choose the initial config step."""
    if not options:
        return "_user"

    # Rewrite frontend statistic card config
    options[CONF_ENTITY_ID] = options.pop("entity")
    options[CONF_PERIOD] = options.pop("period")
    options[CONF_STATE_CHARACTERISTIC] = RECORDER_CHARACTERISTIC_TO_STATS_LTS[
        options.pop("state_type")
    ]

    return None


@callback
def set_period_suggested_values(options: dict[str, Any]) -> str:
    """Add suggested values for editing the period."""

    if calendar_period := options[CONF_PERIOD].get("calendar"):
        options["calendar_offset"] = calendar_period["offset"]
        options["calendar_period"] = calendar_period["period"]
    elif fixed_period := options[CONF_PERIOD].get("fixed_period"):
        options["fixed_period_start_time"] = fixed_period["start_time"]
        options["fixed_period_end_time"] = fixed_period["end_time"]
    else:  # rolling_window
        rolling_window_period = options[CONF_PERIOD]["rolling_window"]
        options["rolling_window_duration"] = rolling_window_period["duration"]
        options["rolling_window_offset"] = rolling_window_period["offset"]

    return "period_type"


@callback
def set_period(
    period_type: str,
) -> Callable[[SchemaCommonFlowHandler, dict[str, Any]], dict[str, Any]]:
    """Set period."""

    @callback
    def _set_period_type(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Add period to user input."""
        # pylint: disable-next=protected-access
        handler._options.pop("calendar_offset", None)
        # pylint: disable-next=protected-access
        handler._options.pop("calendar_period", None)
        # pylint: disable-next=protected-access
        handler._options.pop("fixed_period_start_time", None)
        # pylint: disable-next=protected-access
        handler._options.pop("fixed_period_end_time", None)
        # pylint: disable-next=protected-access
        handler._options.pop("rolling_window_duration", None)
        # pylint: disable-next=protected-access
        handler._options.pop("rolling_window_offset", None)

        if period_type == "calendar":
            period = {
                "calendar": {
                    "offset": user_input.pop("calendar_offset"),
                    "period": user_input.pop("calendar_period"),
                }
            }
        elif period_type == "fixed_period":
            period = {
                "fixed_period": {
                    "start_time": user_input.pop("fixed_period_start_time"),
                    "end_time": user_input.pop("fixed_period_end_time"),
                }
            }
        else:  # period_type = rolling_window
            period = {
                "rolling_window": {
                    "duration": user_input.pop("rolling_window_duration"),
                    "offset": user_input.pop("rolling_window_offset"),
                }
            }
        user_input[CONF_PERIOD] = period
        return user_input

    return _set_period_type


CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(None, next_step=_import_or_user_config),
    "_user": SchemaFlowFormStep(
        CONFIG_SCHEMA_STEP_1, next_step=lambda _: "period_type"
    ),
    "period_type": SchemaFlowMenuStep(PERIOD_TYPES),
    "calendar": SchemaFlowFormStep(CALENDAR_PERIOD_SCHEMA, set_period("calendar")),
    "fixed_period": SchemaFlowFormStep(FIXED_PERIOD_SCHEMA, set_period("fixed_period")),
    "rolling_window": SchemaFlowFormStep(
        ROLLING_WINDOW_PERIOD_SCHEMA, set_period("rolling_window")
    ),
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(
        OPTIONS_SCHEMA_STEP_1, next_step=set_period_suggested_values
    ),
    "period_type": SchemaFlowMenuStep(PERIOD_TYPES),
    "calendar": SchemaFlowFormStep(CALENDAR_PERIOD_SCHEMA, set_period("calendar")),
    "fixed_period": SchemaFlowFormStep(FIXED_PERIOD_SCHEMA, set_period("fixed_period")),
    "rolling_window": SchemaFlowFormStep(
        ROLLING_WINDOW_PERIOD_SCHEMA, set_period("rolling_window")
    ),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Min/Max."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""

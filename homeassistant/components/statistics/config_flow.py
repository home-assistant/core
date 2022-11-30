"""Config flow for Min/Max integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
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
        vol.Required("period"): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_CALENDAR_PERIODS),
        ),
        vol.Required("offset", default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, mode=selector.NumberSelectorMode.BOX),
        ),
    }
)

FIXED_PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required("start_time"): selector.DateTimeSelector(),
        vol.Required("end_time"): selector.DateTimeSelector(),
    }
)

ROLLING_WINDOW_PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required("duration"): selector.DurationSelector(
            selector.DurationSelectorConfig(enable_day=True)
        ),
        vol.Required("offset"): selector.DurationSelector(
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


async def _import_or_user_config(options: dict[str, Any]) -> str | None:
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


def period_suggested_values(
    period_type: str,
) -> Callable[[SchemaCommonFlowHandler], Coroutine[Any, Any, dict[str, Any]]]:
    """Set period."""

    async def _period_suggested_values(
        handler: SchemaCommonFlowHandler,
    ) -> dict[str, Any]:
        """Add suggested values for editing the period."""

        if period_type == "calendar" and (
            calendar_period := handler.options[CONF_PERIOD].get("calendar")
        ):
            return {
                "offset": calendar_period["offset"],
                "period": calendar_period["period"],
            }
        if period_type == "fixed_period" and (
            fixed_period := handler.options[CONF_PERIOD].get("fixed_period")
        ):
            return {
                "start_time": fixed_period["start_time"],
                "end_time": fixed_period["end_time"],
            }
        if period_type == "rolling_window" and (
            rolling_window_period := handler.options[CONF_PERIOD].get("rolling_window")
        ):
            return {
                "duration": rolling_window_period["duration"],
                "offset": rolling_window_period["offset"],
            }

        return {}

    return _period_suggested_values


@callback
def set_period(
    period_type: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]
]:
    """Set period."""

    async def _set_period(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Add period to config entry options."""
        if period_type == "calendar":
            period = {
                "calendar": {
                    "offset": user_input["offset"],
                    "period": user_input["period"],
                }
            }
        elif period_type == "fixed_period":
            period = {
                "fixed_period": {
                    "start_time": user_input["start_time"],
                    "end_time": user_input["end_time"],
                }
            }
        else:  # period_type = rolling_window
            period = {
                "rolling_window": {
                    "duration": user_input.pop("duration"),
                    "offset": user_input.pop("offset"),
                }
            }
        handler.options[CONF_PERIOD] = period
        return {}

    return _set_period


CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(None, next_step=_import_or_user_config),
    "_user": SchemaFlowFormStep(CONFIG_SCHEMA_STEP_1, next_step="period_type"),
    "period_type": SchemaFlowMenuStep(PERIOD_TYPES),
    "calendar": SchemaFlowFormStep(CALENDAR_PERIOD_SCHEMA, set_period("calendar")),
    "fixed_period": SchemaFlowFormStep(FIXED_PERIOD_SCHEMA, set_period("fixed_period")),
    "rolling_window": SchemaFlowFormStep(
        ROLLING_WINDOW_PERIOD_SCHEMA, set_period("rolling_window")
    ),
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA_STEP_1, next_step="period_type"),
    "period_type": SchemaFlowMenuStep(PERIOD_TYPES),
    "calendar": SchemaFlowFormStep(
        CALENDAR_PERIOD_SCHEMA,
        set_period("calendar"),
        suggested_values=period_suggested_values("calendar"),
    ),
    "fixed_period": SchemaFlowFormStep(
        FIXED_PERIOD_SCHEMA,
        set_period("fixed_period"),
        suggested_values=period_suggested_values("fixed_period"),
    ),
    "rolling_window": SchemaFlowFormStep(
        ROLLING_WINDOW_PERIOD_SCHEMA,
        set_period("rolling_window"),
        suggested_values=period_suggested_values("rolling_window"),
    ),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Min/Max."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""

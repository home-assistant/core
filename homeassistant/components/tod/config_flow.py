"""Config flow for Times of the Day integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_AFTER_KIND,
    CONF_AFTER_OFFSET_MIN,
    CONF_AFTER_TIME,
    CONF_BEFORE_KIND,
    CONF_BEFORE_OFFSET_MIN,
    CONF_BEFORE_TIME,
    DOMAIN,
    KIND_FIXED,
    TodKind,
)

_KIND_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=list(TodKind),
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)
_TIME_SELECTOR = selector.TimeSelector()
_OFFSET_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        step=1,
        unit_of_measurement="minutes",
        mode=selector.NumberSelectorMode.BOX,
    )
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_AFTER_KIND, default=KIND_FIXED): _KIND_SELECTOR,
        vol.Required(CONF_BEFORE_KIND, default=KIND_FIXED): _KIND_SELECTOR,
    }
)

STEP_AFTER_FIXED = vol.Schema({vol.Required(CONF_AFTER_TIME): _TIME_SELECTOR})
STEP_AFTER_SUN = vol.Schema(
    {vol.Required(CONF_AFTER_OFFSET_MIN, default=0): _OFFSET_SELECTOR}
)

STEP_BEFORE_FIXED = vol.Schema({vol.Required(CONF_BEFORE_TIME): _TIME_SELECTOR})
STEP_BEFORE_SUN = vol.Schema(
    {vol.Required(CONF_BEFORE_OFFSET_MIN, default=0): _OFFSET_SELECTOR}
)


async def _next_after(data: dict[str, Any]) -> str:
    """Decide which after step to show."""
    return "after_fixed" if data.get(CONF_AFTER_KIND) == KIND_FIXED else "after_sun"


async def _next_before(data: dict[str, Any]) -> str | None:
    """Decide which before step to show."""
    return "before_fixed" if data.get(CONF_BEFORE_KIND) == KIND_FIXED else "before_sun"


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(STEP_USER, next_step=_next_after),
    "after_fixed": SchemaFlowFormStep(STEP_AFTER_FIXED, next_step=_next_before),
    "after_sun": SchemaFlowFormStep(STEP_AFTER_SUN, next_step=_next_before),
    "before_fixed": SchemaFlowFormStep(STEP_BEFORE_FIXED),
    "before_sun": SchemaFlowFormStep(STEP_BEFORE_SUN),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(STEP_USER, next_step=_next_after),
    "after_fixed": SchemaFlowFormStep(STEP_AFTER_FIXED, next_step=_next_before),
    "after_sun": SchemaFlowFormStep(STEP_AFTER_SUN, next_step=_next_before),
    "before_fixed": SchemaFlowFormStep(STEP_BEFORE_FIXED),
    "before_sun": SchemaFlowFormStep(STEP_BEFORE_SUN),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Times of the Day."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])

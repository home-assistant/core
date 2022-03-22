"""Config flow for Utility Meter integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowError,
    HelperFlowStep,
)

from .const import (
    BIMONTHLY,
    CONF_METER_DELTA_VALUES,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFFS,
    DAILY,
    DOMAIN,
    HOURLY,
    MONTHLY,
    QUARTER_HOURLY,
    QUARTERLY,
    WEEKLY,
    YEARLY,
)

METER_TYPES = [
    {"value": "none", "label": "No cycle"},
    {"value": QUARTER_HOURLY, "label": "Every 15 minutes"},
    {"value": HOURLY, "label": "Hourly"},
    {"value": DAILY, "label": "Daily"},
    {"value": WEEKLY, "label": "Weekly"},
    {"value": MONTHLY, "label": "Monthly"},
    {"value": BIMONTHLY, "label": "Every two months"},
    {"value": QUARTERLY, "label": "Quarterly"},
    {"value": YEARLY, "label": "Yearly"},
]


def _validate_config(data: Any) -> Any:
    """Validate config."""
    tariffs: list[str]
    if not data[CONF_TARIFFS]:
        tariffs = []
    else:
        tariffs = data[CONF_TARIFFS].split(",")
    try:
        vol.Unique()(tariffs)
    except vol.Invalid as exc:
        raise HelperFlowError("tariffs_not_unique") from exc

    if cv.time_period_dict(data[CONF_METER_OFFSET]) > timedelta(days=28):
        raise HelperFlowError("offset_max_28_days")

    return data


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_SENSOR): selector.selector(
            {"entity": {"domain": "sensor"}},
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.selector({"text": {}}),
        vol.Required(CONF_SOURCE_SENSOR): selector.selector(
            {"entity": {"domain": "sensor"}},
        ),
        vol.Required(CONF_METER_TYPE): selector.selector(
            {"select": {"options": METER_TYPES}}
        ),
        vol.Required(CONF_METER_OFFSET): selector.selector({"duration": {}}),
        vol.Optional(CONF_TARIFFS): selector.selector({"text": {}}),
        vol.Required(CONF_METER_NET_CONSUMPTION, default=False): selector.selector(
            {"boolean": {}}
        ),
        vol.Required(CONF_METER_DELTA_VALUES, default=False): selector.selector(
            {"boolean": {}}
        ),
    }
)

CONFIG_FLOW = {
    "user": HelperFlowStep(CONFIG_SCHEMA, validate_user_input=_validate_config)
}

OPTIONS_FLOW = {"init": HelperFlowStep(OPTIONS_SCHEMA)}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Utility Meter."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""

        return cast(str, options[CONF_NAME])

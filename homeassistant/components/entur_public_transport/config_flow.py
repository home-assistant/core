"""Config flow for the Entur public transport integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import TextSelector

from .const import (
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_SHOW_ON_MAP,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DEFAULT_NAME,
    DOMAIN,
)


class EnturConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entur public transport."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID].strip()
            if not _is_valid_stop_id(stop_id):
                errors["base"] = "invalid_stop_id"
            else:
                self._async_abort_entries_match({CONF_STOP_IDS: [stop_id]})
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=_entry_data([stop_id]),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_STOP_ID): TextSelector()}
            ),
            errors=errors,
        )

    @override
    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import an Entur platform configuration from YAML."""
        data = dict(import_data)
        data.pop("platform", None)
        stop_ids = data[CONF_STOP_IDS]
        for key, value in _entry_data(stop_ids).items():
            data.setdefault(key, value)
        data[CONF_NAME] = import_data.get(CONF_NAME, DEFAULT_NAME)
        return self.async_create_entry(
            title=data[CONF_NAME],
            data=data,
        )


def _entry_data(stop_ids: list[str]) -> dict[str, Any]:
    """Return default config entry data for a set of stops."""
    return {
        CONF_NAME: DEFAULT_NAME,
        CONF_STOP_IDS: stop_ids,
        CONF_EXPAND_PLATFORMS: True,
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }


def _is_valid_stop_id(stop_id: str) -> bool:
    """Return whether a stop ID is supported by the integration."""
    return any(
        stop_id.startswith(prefix) and stop_id.removeprefix(prefix).isdigit()
        for prefix in ("NSR:StopPlace:", "NSR:Quay:")
    )

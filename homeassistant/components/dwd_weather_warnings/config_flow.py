"""Config flow for the dwd_weather_warnings integration."""

from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    ADVANCE_WARNING_SENSOR,
    CONF_OLD_REGION_NAME,
    CONF_REGION_IDENTIFIER,
    CURRENT_WARNING_SENSOR,
    DEFAULT_MONITORED_CONDITIONS,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
)

CONFIG_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_REGION_IDENTIFIER): cv.string,
        vol.Required(
            CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED_CONDITIONS
        ): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(
                        label="Current warning level",
                        value=CURRENT_WARNING_SENSOR,
                    ),
                    SelectOptionDict(
                        label="Advance warning level",
                        value=ADVANCE_WARNING_SENSOR,
                    ),
                ],
                multiple=True,
            )
        ),
    }
)


class DwdWeatherWarningsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the dwd_weather_warnings integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict = {}

        if user_input is not None:
            # Check, if either CONF_REGION or CONF_GPS_TRACKER has been set.
            if CONF_REGION_IDENTIFIER not in user_input:
                errors["base"] = "no_identifier"
            else:
                # Abort, if a sensor with this name already exists.
                for entry in self._async_current_entries():
                    if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                        return self.async_abort(reason="already_configured")

                # Monitor all conditions by default, if none are set.
                if not user_input[CONF_MONITORED_CONDITIONS]:
                    user_input[CONF_MONITORED_CONDITIONS] = DEFAULT_MONITORED_CONDITIONS

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", errors=errors, data_schema=CONFIG_SCHEMA
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        LOGGER.debug(
            "Starting import of sensor from configuration.yaml - %s", import_config
        )

        # Adjust data to new format.
        region_identifier = import_config.pop(CONF_OLD_REGION_NAME)
        import_config[CONF_REGION_IDENTIFIER] = region_identifier

        if CONF_NAME not in import_config:
            import_config[CONF_NAME] = DEFAULT_NAME

        if CONF_MONITORED_CONDITIONS not in import_config:
            import_config[CONF_MONITORED_CONDITIONS] = DEFAULT_MONITORED_CONDITIONS

        # Abort, if a sensor with this name already exists.
        for entry in self._async_current_entries():
            if entry.data[CONF_NAME] == import_config[CONF_NAME]:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )

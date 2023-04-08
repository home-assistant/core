"""Config flow for the dwd_weather_warnings integration."""

from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_OLD_REGION_NAME,
    CONF_REGION_IDENTIFIER,
    DEFAULT_MONITORED_CONDITIONS,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
)

CONFIG_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_REGION_IDENTIFIER): cv.string,
    }
)


class DwdWeatherWarningsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the dwd_weather_warnings integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Set the unique ID for this config entry.
            await self.async_set_unique_id(user_input[CONF_REGION_IDENTIFIER])
            self._abort_if_unique_id_configured()

            # Set the name for this config entry.
            user_input[
                CONF_NAME
            ] = f"{DEFAULT_NAME} {user_input[CONF_REGION_IDENTIFIER]}"

            # Monitor all conditions by default.
            user_input[CONF_MONITORED_CONDITIONS] = DEFAULT_MONITORED_CONDITIONS

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        LOGGER.debug(
            "Starting import of sensor from configuration.yaml - %s", import_config
        )

        # Adjust data to new format.
        region_identifier = import_config.pop(CONF_OLD_REGION_NAME)
        import_config[CONF_REGION_IDENTIFIER] = region_identifier

        if CONF_NAME not in import_config:
            import_config[
                CONF_NAME
            ] = f"{DEFAULT_NAME} {import_config[CONF_REGION_IDENTIFIER]}"

        # Set the unique ID for this imported entry.
        await self.async_set_unique_id(import_config[CONF_REGION_IDENTIFIER])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )

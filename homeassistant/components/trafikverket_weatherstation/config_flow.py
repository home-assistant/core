"""Adds config flow for Trafikverket Weather integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import CONF_STATION, DOMAIN
from .sensor import SENSOR_TYPES

SENSOR_LIST: dict[str, str | None] = {
    description.key: description.name for (description) in SENSOR_TYPES
}

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_STATION): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): cv.multi_select(
            SENSOR_LIST
        ),
    }
)


class TVWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Weatherstation integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry

    async def async_step_import(self, config: dict):
        """Import a configuration from config.yaml."""

        self.context.update(
            {"title_placeholders": {CONF_NAME: f"YAML import {DOMAIN}"}}
        )

        self._async_abort_entries_match({CONF_NAME: config[CONF_NAME]})
        return await self.async_step_user(user_input=config)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            api_key = user_input[CONF_API_KEY]
            station = user_input[CONF_STATION]
            conditions = user_input[CONF_MONITORED_CONDITIONS]

            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME: name,
                    CONF_API_KEY: api_key,
                    CONF_STATION: station,
                    CONF_MONITORED_CONDITIONS: conditions,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

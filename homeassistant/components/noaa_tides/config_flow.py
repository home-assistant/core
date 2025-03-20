"""Config flow for the NOAA Tides."""

from typing import Any

from noaa_coops.station import Station
from requests.exceptions import ConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TIME_ZONE, CONF_UNIT_SYSTEM
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_STATION_ID, DEFAULT_TIMEZONE, DOMAIN, TIMEZONES, UNIT_SYSTEMS
from .helpers import get_default_unit_system, get_station_unique_id

DATA_SCHEMA_DICT = {
    vol.Required(
        CONF_STATION_ID,
    ): str,
}


def get_options_schema_dict(hass: HomeAssistant | None = None):
    """Return options schema dict."""
    return {
        vol.Optional(
            CONF_UNIT_SYSTEM,
            default=get_default_unit_system(hass),
        ): SelectSelector(
            SelectSelectorConfig(
                {
                    "options": UNIT_SYSTEMS,
                    "translation_key": "unit_systems",
                }
            )
        ),
        vol.Optional(CONF_TIME_ZONE, default=DEFAULT_TIMEZONE): SelectSelector(
            SelectSelectorConfig(
                {
                    "options": TIMEZONES,
                    "translation_key": "timezones",
                }
            )
        ),
    }


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(vol.Schema(get_options_schema_dict())),
}


class NoaaTidesConfigFlow(ConfigFlow, domain=DOMAIN):
    """NOAA Tides config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""

        errors: dict[str, str] | None = None
        suggested_values: dict[str, Any] = self.init_data

        input_schema = vol.Schema(DATA_SCHEMA_DICT).extend(
            get_options_schema_dict(self.hass)
        )

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]

            unique_id = get_station_unique_id(station_id)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            unit_system = user_input.get(
                CONF_UNIT_SYSTEM, get_default_unit_system(self.hass)
            )
            timezone = user_input.get(CONF_TIME_ZONE, DEFAULT_TIMEZONE)

            try:
                station = await self.hass.async_add_executor_job(
                    Station, station_id, unit_system
                )
            except KeyError:
                errors = {"base": "station_not_found"}
                suggested_values = user_input
            except ConnectionError:
                errors = {"base": "cannot_connect"}
                suggested_values = user_input
            else:
                return self.async_create_entry(
                    title=f"{station.name} ({station_id})",
                    data={
                        CONF_STATION_ID: station_id,
                    },
                    options={
                        CONF_UNIT_SYSTEM: unit_system,
                        CONF_TIME_ZONE: timezone,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                input_schema, suggested_values
            ),
            errors=errors,
        )

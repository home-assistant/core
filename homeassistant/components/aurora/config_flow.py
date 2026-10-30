"""Config flow for Aurora."""

import logging
from typing import Any, override

from aiohttp import ClientError
from auroranoaa import AuroraForecast
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import CONF_THRESHOLD, DEFAULT_THRESHOLD, DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_THRESHOLD, default=DEFAULT_THRESHOLD): probatio.All(
            probatio.Coerce(int), probatio.Percentage()
        ),
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class AuroraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NOAA Aurora Integration."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]

            session = aiohttp_client.async_get_clientsession(self.hass)
            api = AuroraForecast(session=session)

            try:
                await api.get_forecast_data(
                    location[CONF_LONGITUDE], location[CONF_LATITUDE]
                )
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{location[CONF_LONGITUDE]}_{location[CONF_LATITUDE]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Aurora visibility", data=location)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=False)
                        ),
                    }
                ),
                {
                    CONF_LOCATION: {
                        CONF_LONGITUDE: self.hass.config.longitude,
                        CONF_LATITUDE: self.hass.config.latitude,
                    }
                },
            ),
            errors=errors,
        )

"""Adds config flow for Nederlandse Spoorwegen."""

import asyncio

import ns_api
from ns_api import RequestParametersError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import selector
from homeassistant.const import CONF_API_KEY

from .const import CONF_STATION_FROM, CONF_STATION_TO, CONF_STATION_VIA, DOMAIN


class NederlandseSpoorwegenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Nederlandse Spoorwegen config flow."""

    # VERSION = 1
    # MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""

        self.api_key: str
        self._stations: None

    async def async_step_user(self, user_input) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]
            try:
                nsapi = ns_api.NSAPI(self.api_key)
                loop = asyncio.get_running_loop()
                station_data = await loop.run_in_executor(None, nsapi.get_stations)
                self._stations = {
                    station.code: station.names["long"]
                    for station in station_data
                    if station.country == "NL"
                }
                self._stations = dict(
                    sorted(self._stations.items(), key=lambda item: item[1])
                )
            except RequestParametersError:
                errors["base"] = "invalid_api_key"
            else:
                return await self.async_step_stations()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_stations(self, user_input=None) -> ConfigFlowResult:
        """Handle the step to add stations."""
        if user_input is not None:
            await self.async_set_unique_id(
                user_input[CONF_STATION_FROM] + user_input[CONF_STATION_TO]
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_STATION_FROM] + user_input[CONF_STATION_TO],
                data={
                    CONF_API_KEY: self.api_key,
                    CONF_STATION_FROM: user_input[CONF_STATION_FROM],
                    CONF_STATION_VIA: user_input.get(CONF_STATION_VIA, None),
                    CONF_STATION_TO: user_input[CONF_STATION_TO],
                },
            )

        return self.async_show_form(
            step_id="stations",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_FROM): vol.In(self._stations),
                    vol.Optional(CONF_STATION_VIA): vol.In(self._stations),
                    vol.Required(CONF_STATION_TO): vol.In(self._stations),
                }
            ),
        )

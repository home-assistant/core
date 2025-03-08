"""Adds config flow for Nederlandse Spoorwegen."""

import asyncio
from typing import Any

import ns_api
from ns_api import RequestParametersError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import TimeSelector

from .const import (
    CONF_STATION_FROM,
    CONF_STATION_TO,
    CONF_STATION_VIA,
    CONF_TIME,
    DOMAIN,
)


async def get_stations(nsapi: ns_api.NSAPI):
    """Return all available stations."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, nsapi.get_stations)


class NederlandseSpoorwegenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Nederlandse Spoorwegen config flow."""

    # VERSION = 1
    # MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""

        self.api_key: str
        self._stations: None
        self._stations_short: None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"trip": NederlandseSpoorwegenSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]
            try:
                await get_stations(ns_api.NSAPI(self.api_key))
            except RequestParametersError:
                errors["base"] = "invalid_api_key"
            else:
                await self.async_set_unique_id(self.api_key)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="NS API", data={CONF_API_KEY: self.api_key}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class NederlandseSpoorwegenSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a location."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._stations = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new train."""

        if self._stations is None:
            nsapi = self.hass.config_entries.async_get_known_entry(
                self.handler[0]
            ).runtime_data.nsapi

            self._stations = {
                station.code: station.names["middle"]
                for station in await get_stations(nsapi)
                if station.country == "NL"
            }

            self._stations = dict(
                sorted(self._stations.items(), key=lambda item: item[1])
            )

        errors: dict[str, str] = {}

        if user_input is not None:
            title = user_input.get(CONF_NAME, None)

            if title is None:
                title = self._stations[user_input[CONF_STATION_FROM]]
                if CONF_STATION_VIA in user_input:
                    title = title + " - " + self._stations[user_input[CONF_STATION_VIA]]
                title = title + " - " + self._stations[user_input[CONF_STATION_TO]]
                if CONF_TIME in user_input:
                    title = title + " - " + user_input[CONF_TIME]

            return self.async_create_entry(
                title=title,
                data={
                    CONF_STATION_FROM: user_input[CONF_STATION_FROM],
                    CONF_STATION_VIA: user_input.get(CONF_STATION_VIA, None),
                    CONF_STATION_TO: user_input[CONF_STATION_TO],
                    CONF_TIME: user_input.get(CONF_TIME, None),
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME): str,
                    vol.Required(CONF_STATION_FROM): vol.In(self._stations),
                    vol.Optional(CONF_STATION_VIA): vol.In(self._stations),
                    vol.Required(CONF_STATION_TO): vol.In(self._stations),
                    vol.Optional(CONF_TIME): TimeSelector(),
                }
            ),
            errors=errors,
        )

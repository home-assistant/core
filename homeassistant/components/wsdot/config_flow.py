"""Adds config flow for wsdot."""

import logging
from types import MappingProxyType
from typing import Any

from aiohttp.client_exceptions import ClientError
import voluptuous as vol
import wsdot as wsdot_api

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.selector import selector

from .const import CONF_TRAVEL_TIMES, DOMAIN, SUBENTRY_TRAVEL_TIMES

_LOGGER = logging.getLogger(__name__)


class InvalidApiKeyError(ClientError):
    """Exception indicating the user entered an invalid API Key."""


class WSDOTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for WSDOT."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            wsdot_travel_times = wsdot_api.WsdotTravelTimes(
                user_input[CONF_API_KEY]
            )
            try:
                await wsdot_travel_times.get_all_travel_times()
            except wsdot_api.WsdotTravelError as ws_error:
                if ws_error.status == 400:
                    errors[CONF_API_KEY] = "invalid_api_key"
                else:
                    errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_API_KEY])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initialized by import."""
        await self.async_set_unique_id(import_info[CONF_API_KEY])
        self._abort_if_unique_id_configured()
        wsdot_travel_times = wsdot_api.WsdotTravelTimes(import_info[CONF_API_KEY])
        try:
            travel_time_routes = await wsdot_travel_times.get_all_travel_times()
        except wsdot_api.WsdotTravelError as ws_error:
            if ws_error.status == 400:
                return self.async_abort(reason="invalid_api_key")
            return self.async_abort(reason="cannot_connect")

        subentries = []
        for route in import_info[CONF_TRAVEL_TIMES]:
            maybe_travel_time = [
                tt
                for tt in travel_time_routes
                # old platform configs could store the id as either a str or an int
                if str(tt.TravelTimeID) == str(route[CONF_ID])
            ]
            if not maybe_travel_time:
                _LOGGER.error(
                    "Found legacy WSDOT travel_time that does not describe a valid travel_time route (%s)",
                    route,
                )
                continue
            travel_time = maybe_travel_time[0]
            route_name = travel_time.Name
            unique_id = "_".join(travel_time.Name.split())
            subentries.append(
                ConfigSubentry(
                    subentry_type=SUBENTRY_TRAVEL_TIMES,
                    unique_id=unique_id,
                    title=route_name,
                    data=MappingProxyType(
                        {CONF_NAME: travel_time.Name, CONF_ID: travel_time.TravelTimeID}
                    ),
                ).as_dict()
            )

        return self.async_create_entry(
            title=DOMAIN,
            data={
                CONF_API_KEY: import_info[CONF_API_KEY],
            },
            subentries=subentries,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by wsdot."""
        return {SUBENTRY_TRAVEL_TIMES: TravelTimeSubentryFlowHandler}


class TravelTimeSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding WSDOT Travel Times."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new Travel Time subentry."""
        runtime = self._get_entry().runtime_data
        if runtime is None:
            raise ConfigEntryError("WSDOT entry has no runtime_data")
        travel_times = await runtime.wsdot_travel_times.get_all_travel_times()
        if user_input is not None:
            route = [
                {CONF_NAME: tt.Name, CONF_ID: tt.TravelTimeID}
                for tt in travel_times
                if tt.Name == user_input[CONF_NAME]
            ][0]
            name = route[CONF_NAME]
            unique_id = "_".join(name.split())
            return self.async_create_entry(title=name, unique_id=unique_id, data=route)

        names = sorted(tt.Name for tt in travel_times)
        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): selector(
                        {"select": {"options": names, "mode": "dropdown"}}
                    ),
                }
            ),
            errors={},
        )

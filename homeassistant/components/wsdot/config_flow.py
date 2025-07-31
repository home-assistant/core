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
from homeassistant.helpers.selector import selector

from .const import (
    CONF_TRAVEL_TIMES,
    DIALOG_API_KEY,
    DIALOG_NAME,
    DIALOG_ROUTE,
    DOMAIN,
    SUBENTRY_TRAVEL_TIMES,
)

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
            try:
                wsdot_travel_times = wsdot_api.WsdotTravelTimes(
                    user_input[DIALOG_API_KEY]
                )
                travel_time_routes = await wsdot_travel_times.get_all_travel_times()
            except wsdot_api.WsdotTravelError as ws_error:
                if ws_error.status == 400:
                    errors[DIALOG_API_KEY] = (
                        "Invalid API Key. If you do not have an API Key, you can get a new one at https://wsdot.wa.gov/traffic/api/"
                    )
                else:
                    err_msg = "Unable to retrieve routes from WSDOT"
                    _LOGGER.exception(err_msg)
                    errors["base"] = err_msg
            else:
                return self.async_create_entry(
                    title=user_input[DIALOG_NAME],
                    data={
                        CONF_API_KEY: user_input[DIALOG_API_KEY],
                        CONF_TRAVEL_TIMES: [
                            {"id": t.TravelTimeID, "name": t.Name}
                            for t in travel_time_routes
                        ],
                    },
                )

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema(
                {
                    vol.Required(DIALOG_API_KEY): str,
                    vol.Required(DIALOG_NAME, default=DOMAIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initialized by import."""
        try:
            wsdot_travel_times = wsdot_api.WsdotTravelTimes(import_info[CONF_API_KEY])
            travel_time_routes = await wsdot_travel_times.get_all_travel_times()
        except wsdot_api.WsdotTravelError as ws_error:
            if ws_error.status == 400:
                reason = "Invalid API Key"
            else:
                reason = "unable to retrieve WSDOT routes"
            return self.async_abort(reason=reason)

        subentries = []
        for route in import_info[CONF_TRAVEL_TIMES]:
            maybe_travel_time = [
                tt
                for tt in travel_time_routes
                if str(tt.TravelTimeID) == str(route[CONF_ID])
            ]
            if not maybe_travel_time:
                _LOGGER.error(
                    "Found legacy WSDOT travel_time that does not describe a valid travel_time route (%s)",
                    route,
                )
                continue
            travel_time = maybe_travel_time[0]
            route_name = route.get(CONF_NAME, travel_time.Name)
            unique_id = "_".join((DOMAIN, *travel_time.Name.split()))
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
                CONF_TRAVEL_TIMES: [
                    {"id": t.TravelTimeID, "name": t.Name} for t in travel_time_routes
                ],
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
        travel_times = self._get_entry().data[CONF_TRAVEL_TIMES]
        if user_input is not None:
            route = [
                tt for tt in travel_times if tt[CONF_NAME] == user_input[DIALOG_ROUTE]
            ][0]
            title = user_input[DIALOG_NAME] or route[CONF_NAME]
            return self.async_create_entry(title=title, data=route)

        names = sorted(tt[CONF_NAME] for tt in travel_times)
        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema(
                {
                    vol.Optional(DIALOG_NAME, default=""): str,
                    vol.Required(DIALOG_ROUTE): selector(
                        {"select": {"options": names, "mode": "dropdown"}}
                    ),
                }
            ),
            errors={},
        )

"""Adds config flow for wsdot."""

import logging
from types import MappingProxyType
from typing import Any

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
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_TRAVEL_TIMES, DOMAIN, SUBENTRY_TRAVEL_TIMES

_LOGGER = logging.getLogger(__name__)


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
            data = {CONF_API_KEY: user_input[CONF_API_KEY]}
            self._async_abort_entries_match(data)
            wsdot_travel_times = wsdot_api.WsdotTravelTimes(user_input[CONF_API_KEY])
            try:
                await wsdot_travel_times.get_all_travel_times()
            except wsdot_api.WsdotTravelError as ws_error:
                if ws_error.status == 400:
                    errors[CONF_API_KEY] = "invalid_api_key"
                else:
                    errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=DOMAIN,
                    data=data,
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
        self._async_abort_entries_match({CONF_API_KEY: import_info[CONF_API_KEY]})
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
                return self.async_abort(reason="invalid_travel_time_id")
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

    def __init__(self, *args, **kwargs) -> None:
        """Initialize TravelTimeSubentryFlowHandler."""
        super().__init__(*args, **kwargs)
        self.travel_times: dict[str, int] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new Travel Time subentry."""
        if self.travel_times is None:
            client = self._get_entry().runtime_data
            travel_times = await client.get_all_travel_times()
            self.travel_times = {tt.Name: tt.TravelTimeID for tt in travel_times}

        if user_input is not None:
            name = user_input[CONF_NAME]
            tt_id = self.travel_times[name]
            unique_id = str(tt_id)
            data = {CONF_NAME: name, CONF_ID: tt_id}
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                for subentry in entry.subentries.values():
                    if subentry.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")
            return self.async_create_entry(title=name, unique_id=unique_id, data=data)

        names = SelectSelector(
            SelectSelectorConfig(
                options=list(self.travel_times.keys()),
                sort=True,
            )
        )
        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema({vol.Required(CONF_NAME): names}),
            errors={},
        )

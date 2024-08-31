"""Config flow for HVV integration."""

from __future__ import annotations

import logging
from typing import Any

from pygti.auth import GTI_DEFAULT_HOST
from pygti.exceptions import CannotConnect, InvalidAuth
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_OFFSET, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv

from .const import CONF_FILTER, CONF_REAL_TIME, CONF_STATION, DOMAIN
from .hub import GTIHub

_LOGGER = logging.getLogger(__name__)

SCHEMA_STEP_USER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=GTI_DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

SCHEMA_STEP_STATION = vol.Schema({vol.Required(CONF_STATION): str})

SCHEMA_STEP_OPTIONS = vol.Schema(
    {
        vol.Required(CONF_FILTER): vol.In([]),
        vol.Required(CONF_OFFSET, default=0): cv.positive_int,
        vol.Optional(CONF_REAL_TIME, default=True): bool,
    }
)


class HVVDeparturesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HVV."""

    VERSION = 1

    hub: GTIHub
    data: dict[str, Any]

    def __init__(self) -> None:
        """Initialize component."""
        self.stations: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            self.hub = GTIHub(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session,
            )

            try:
                response = await self.hub.authenticate()
                _LOGGER.debug("Init gti: %r", response)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"

            if not errors:
                self.data = user_input
                return await self.async_step_station()

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_STEP_USER, errors=errors
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step where the user inputs his/her station."""
        if user_input is not None:
            errors = {}

            check_name = await self.hub.gti.checkName(
                {"theName": {"name": user_input[CONF_STATION]}, "maxList": 20}
            )

            stations = check_name.get("results")

            self.stations = {
                f"{station.get('name')}": station
                for station in stations
                if station.get("type") == "STATION"
            }

            if not self.stations:
                errors["base"] = "no_results"

                return self.async_show_form(
                    step_id="station", data_schema=SCHEMA_STEP_STATION, errors=errors
                )

            # schema

            return await self.async_step_station_select()

        return self.async_show_form(step_id="station", data_schema=SCHEMA_STEP_STATION)

    async def async_step_station_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step where the user inputs his/her station."""

        schema = vol.Schema({vol.Required(CONF_STATION): vol.In(list(self.stations))})

        if user_input is None:
            return self.async_show_form(step_id="station_select", data_schema=schema)

        self.data.update({"station": self.stations[user_input[CONF_STATION]]})

        title = self.data[CONF_STATION]["name"]

        return self.async_create_entry(title=title, data=self.data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize HVV Departures options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.departure_filters: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}
        if not self.departure_filters:
            departure_list = {}
            hub: GTIHub = self.hass.data[DOMAIN][self.config_entry.entry_id]

            try:
                departure_list = await hub.gti.departureList(
                    {
                        "station": {
                            "type": "STATION",
                            "id": self.config_entry.data[CONF_STATION].get("id"),
                        },
                        "time": {"date": "heute", "time": "jetzt"},
                        "maxList": 5,
                        "maxTimeOffset": 200,
                        "useRealtime": True,
                        "returnFilters": True,
                    }
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"

            if not errors:
                self.departure_filters = {
                    str(i): departure_filter
                    for i, departure_filter in enumerate(departure_list["filter"])
                }

        if user_input is not None and not errors:
            options = {
                CONF_FILTER: [
                    self.departure_filters[x] for x in user_input[CONF_FILTER]
                ],
                CONF_OFFSET: user_input[CONF_OFFSET],
                CONF_REAL_TIME: user_input[CONF_REAL_TIME],
            }

            return self.async_create_entry(title="", data=options)

        if CONF_FILTER in self.config_entry.options:
            old_filter = [
                i
                for (i, f) in self.departure_filters.items()
                if f in self.config_entry.options[CONF_FILTER]
            ]
        else:
            old_filter = []

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_FILTER, default=old_filter): cv.multi_select(
                        {
                            key: (
                                f"{departure_filter['serviceName']},"
                                f" {departure_filter['label']}"
                            )
                            for key, departure_filter in self.departure_filters.items()
                        }
                    ),
                    vol.Required(
                        CONF_OFFSET,
                        default=self.config_entry.options.get(CONF_OFFSET, 0),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_REAL_TIME,
                        default=self.config_entry.options.get(CONF_REAL_TIME, True),
                    ): bool,
                }
            ),
            errors=errors,
        )

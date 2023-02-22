"""Adds config flow for Trafikverket Train integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytrafikverket import TrafikverketTrain
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from .const import CONF_FROM, CONF_TIME, CONF_TO, DOMAIN
from .util import create_unique_id

ERROR_INVALID_AUTH = "Source: Security, message: Invalid authentication"
ERROR_INVALID_STATION = "Could not find a station with the specified name"
ERROR_MULTIPLE_STATION = "Found multiple stations with the specified name"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_TIME): cv.string,
        vol.Required(CONF_WEEKDAY, default=WEEKDAYS): cv.multi_select(
            {day: day for day in WEEKDAYS}
        ),
    }
)
DATA_SCHEMA_REAUTH = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


class TVTrainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Train integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry | None

    async def validate_input(
        self, api_key: str, train_from: str, train_to: str
    ) -> None:
        """Validate input from user input."""
        web_session = async_get_clientsession(self.hass)
        train_api = TrafikverketTrain(web_session, api_key)
        await train_api.async_get_train_station(train_from)
        await train_api.async_get_train_station(train_to)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication with Trafikverket."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Trafikverket."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]

            assert self.entry is not None
            try:
                await self.validate_input(
                    api_key, self.entry.data[CONF_FROM], self.entry.data[CONF_TO]
                )
            except ValueError as err:
                if str(err) == ERROR_INVALID_AUTH:
                    errors["base"] = "invalid_auth"
                elif str(err) == ERROR_INVALID_STATION:
                    errors["base"] = "invalid_station"
                elif str(err) == ERROR_MULTIPLE_STATION:
                    errors["base"] = "more_stations"
                else:
                    errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_API_KEY: api_key,
                    },
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA_REAUTH,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key: str = user_input[CONF_API_KEY]
            train_from: str = user_input[CONF_FROM]
            train_to: str = user_input[CONF_TO]
            train_time: str | None = user_input.get(CONF_TIME)
            train_days: list = user_input[CONF_WEEKDAY]

            name = f"{train_from} to {train_to}"
            if train_time:
                name = f"{train_from} to {train_to} at {train_time}"

            try:
                await self.validate_input(api_key, train_from, train_to)
            except ValueError as err:
                if str(err) == ERROR_INVALID_AUTH:
                    errors["base"] = "invalid_auth"
                elif str(err) == ERROR_INVALID_STATION:
                    errors["base"] = "invalid_station"
                elif str(err) == ERROR_MULTIPLE_STATION:
                    errors["base"] = "more_stations"
                else:
                    errors["base"] = "cannot_connect"
            else:
                if train_time:
                    if bool(dt_util.parse_time(train_time) is None):
                        errors["base"] = "invalid_time"
                if not errors:
                    unique_id = create_unique_id(
                        train_from, train_to, train_time, train_days
                    )
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_API_KEY: api_key,
                            CONF_NAME: name,
                            CONF_FROM: train_from,
                            CONF_TO: train_to,
                            CONF_TIME: train_time,
                            CONF_WEEKDAY: train_days,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

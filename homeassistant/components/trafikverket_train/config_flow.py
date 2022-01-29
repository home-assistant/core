"""Adds config flow for Trafikverket Train integration."""
from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)

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


class TVTrainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Train integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry

    async def validate_input(
        self, sensor_api: str, train_from: str, train_to: str
    ) -> str:
        """Validate input from user input."""
        web_session = async_get_clientsession(self.hass)
        train_api = TrafikverketTrain(web_session, sensor_api)
        try:
            await train_api.async_get_train_station(train_from)
            await train_api.async_get_train_station(train_to)
        except ValueError as err:
            return str(err)
        return "connected"

    async def async_step_import(self, config: dict[str, Any] | None) -> FlowResult:
        """Import a configuration from config.yaml."""

        self._async_abort_entries_match(config)
        return await self.async_step_user(user_input=config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            train_from = user_input[CONF_FROM]
            train_to = user_input[CONF_TO]
            train_time = user_input.get(CONF_TIME)
            train_days = user_input[CONF_WEEKDAY]

            name = (
                f"{train_from} to {train_to} at {train_time}"
                if train_time
                else f"{train_from} to {train_to}"
            )

            validate = await self.validate_input(api_key, train_from, train_to)

            if train_time:
                validate = (
                    "Invalid time"
                    if bool(dt_util.parse_time(train_time) is None)
                    else validate
                )

            if validate == "connected":
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
            if validate == "Source: Security, message: Invalid authentication":
                errors["base"] = "invalid_auth"
            elif validate == "Could not find a station with the specified name":
                errors["base"] = "invalid_station"
            elif validate == "Found multiple stations with the specified name":
                errors["base"] = "more_stations"
            elif validate == "Invalid time":
                errors["base"] = "invalid_time"
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

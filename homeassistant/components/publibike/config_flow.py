"""Config flow for the PubliBike Public API integration."""

from __future__ import annotations

import logging

from pypublibike.publibike import PubliBike
from requests import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    BATTERY_LIMIT,
    BATTERY_LIMIT_DEFAULT,
    DOMAIN,
    LATITUDE,
    LONGITUDE,
    STATION_ID,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(BATTERY_LIMIT, default=BATTERY_LIMIT_DEFAULT): vol.All(
            cv.positive_int, vol.Range(1, 100)
        ),
        vol.Optional(STATION_ID): cv.positive_int,
        vol.Optional(LATITUDE): cv.latitude,
        vol.Optional(LONGITUDE): cv.longitude,
    }
)


class PubliBikeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PubliBike integration."""

    VERSION = 1

    async def _is_valid_station_id(self, _id) -> bool:
        publi_bike = PubliBike()
        all_station_ids = [
            s.stationId
            for s in await self.hass.async_add_executor_job(publi_bike.getStations)
        ]
        return bool(_id in all_station_ids)

    async def async_step_user(
        self, user_input: dict[str, int] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""

        errors = {}

        if user_input is not None:
            station_id = user_input.get(STATION_ID)
            if station_id is not None:
                try:
                    id_valid = await self._is_valid_station_id(station_id)
                except RequestException as e:
                    _LOGGER.error("Unable to connect to the PubliBike API: %s", str(e))
                    return self.async_show_form(
                        step_id="user",
                        data_schema=DATA_SCHEMA,
                        errors={"base": "connection_error"},
                    )
                if not id_valid:
                    errors["base"] = "invalid_id"

            if not errors:
                return self.async_create_entry(
                    title="PubliBike",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

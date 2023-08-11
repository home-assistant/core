"""Config flow for the PubliBike Public API integration."""

from __future__ import annotations

import logging
from typing import Optional

from pypublibike.publibike import PubliBike, Station
from requests import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
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
        vol.Optional(STATION_ID): cv.positive_int,
    }
)


class PubliBikeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config_old flow for PubliBike integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return PubliBikeOptionsFlowHandler(config_entry)

    async def _is_valid_station_id(self, station_id: int) -> bool:
        publi_bike = PubliBike()
        all_station_ids = [
            s.stationId
            for s in await self.hass.async_add_executor_job(publi_bike.getStations)
        ]
        return station_id in all_station_ids

    async def _get_station_name(self, station_id: Optional[int]) -> str:
        station = Station(stationId=station_id)
        await self.hass.async_add_executor_job(station.refresh)
        return station.name

    async def async_step_user(
        self, user_input: dict[str, int] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""

        errors = {}

        if user_input is not None:
            if (station_id := user_input.get(STATION_ID)) is not None:
                try:
                    if not await self._is_valid_station_id(station_id):
                        errors["base"] = "invalid_id"
                except RequestException:
                    errors["base"] = "connection_error"
                    _LOGGER.exception("Unable to connect to the PubliBike API")
                except Exception:  # pylint: disable=broad-except
                    errors["base"] = "unknown"
                    _LOGGER.exception(
                        "Unknown exception occurred while validating the station id"
                    )

            if not errors:
                station_name = await self._get_station_name(station_id)
                return self.async_create_entry(
                    title=f"PubliBike - {station_name}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class PubliBikeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a PubliBike options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(BATTERY_LIMIT, default=BATTERY_LIMIT_DEFAULT): vol.All(
                        cv.positive_int, vol.Range(1, 100)
                    ),
                    vol.Optional(LATITUDE): cv.latitude,
                    vol.Optional(LONGITUDE): cv.longitude,
                }
            ),
        )

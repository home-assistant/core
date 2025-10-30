"""Config flow for World Air Quality Index (WAQI) integration."""

from __future__ import annotations

import logging
from typing import Any

from aiowaqi import (
    WAQIAirQuality,
    WAQIAuthenticationError,
    WAQIClient,
    WAQIConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from .const import CONF_STATION_NUMBER, DOMAIN, SUBENTRY_TYPE_STATION

_LOGGER = logging.getLogger(__name__)

CONF_MAP = "map"


async def get_by_station_number(
    client: WAQIClient, station_number: int
) -> tuple[WAQIAirQuality | None, dict[str, str]]:
    """Get measuring station by station number."""
    errors: dict[str, str] = {}
    measuring_station: WAQIAirQuality | None = None
    try:
        measuring_station = await client.get_by_station_number(station_number)
    except WAQIConnectionError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    return measuring_station, errors


class WAQIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for World Air Quality Index (WAQI)."""

    VERSION = 2

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_STATION: StationFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            client = WAQIClient(session=async_get_clientsession(self.hass))
            client.authenticate(user_input[CONF_API_KEY])
            try:
                await client.get_by_ip()
            except WAQIAuthenticationError:
                errors["base"] = "invalid_auth"
            except WAQIConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="World Air Quality Index",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class StationFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a sensor subentry."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["map", "station_number"],
        )

    async def async_step_map(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add measuring station via map."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = WAQIClient(session=async_get_clientsession(self.hass))
            client.authenticate(self._get_entry().data[CONF_API_KEY])
            try:
                measuring_station = await client.get_by_coordinates(
                    user_input[CONF_LOCATION][CONF_LATITUDE],
                    user_input[CONF_LOCATION][CONF_LONGITUDE],
                )
            except WAQIConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self._async_create_entry(measuring_station)
        return self.async_show_form(
            step_id=CONF_MAP,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LOCATION): LocationSelector(),
                    }
                ),
                {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            errors=errors,
        )

    async def async_step_station_number(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add measuring station via station number."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = WAQIClient(session=async_get_clientsession(self.hass))
            client.authenticate(self._get_entry().data[CONF_API_KEY])
            station_number = user_input[CONF_STATION_NUMBER]
            measuring_station, errors = await get_by_station_number(
                client, abs(station_number)
            )
            if not measuring_station:
                measuring_station, _ = await get_by_station_number(
                    client,
                    abs(station_number) - station_number - station_number,
                )
            if measuring_station:
                return await self._async_create_entry(measuring_station)
        return self.async_show_form(
            step_id=CONF_STATION_NUMBER,
            data_schema=vol.Schema({vol.Required(CONF_STATION_NUMBER): int}),
            errors=errors,
        )

    async def _async_create_entry(
        self, measuring_station: WAQIAirQuality
    ) -> SubentryFlowResult:
        station_id = str(measuring_station.station_id)
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            for subentry in entry.subentries.values():
                if subentry.unique_id == station_id:
                    return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=measuring_station.city.name,
            data={
                CONF_STATION_NUMBER: measuring_station.station_id,
            },
            unique_id=station_id,
        )

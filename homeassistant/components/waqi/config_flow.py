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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_METHOD,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_STATION_NUMBER, DOMAIN

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

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            async with WAQIClient(
                session=async_get_clientsession(self.hass)
            ) as waqi_client:
                waqi_client.authenticate(user_input[CONF_API_KEY])
                try:
                    await waqi_client.get_by_ip()
                except WAQIAuthenticationError:
                    errors["base"] = "invalid_auth"
                except WAQIConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    self.data = user_input
                    if user_input[CONF_METHOD] == CONF_MAP:
                        return await self.async_step_map()
                    return await self.async_step_station_number()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_METHOD): SelectSelector(
                        SelectSelectorConfig(
                            options=[CONF_MAP, CONF_STATION_NUMBER],
                            translation_key="method",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_map(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add measuring station via map."""
        errors: dict[str, str] = {}
        if user_input is not None:
            async with WAQIClient(
                session=async_get_clientsession(self.hass)
            ) as waqi_client:
                waqi_client.authenticate(self.data[CONF_API_KEY])
                try:
                    measuring_station = await waqi_client.get_by_coordinates(
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
                        vol.Required(
                            CONF_LOCATION,
                        ): LocationSelector(),
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
    ) -> ConfigFlowResult:
        """Add measuring station via station number."""
        errors: dict[str, str] = {}
        if user_input is not None:
            async with WAQIClient(
                session=async_get_clientsession(self.hass)
            ) as waqi_client:
                waqi_client.authenticate(self.data[CONF_API_KEY])
                station_number = user_input[CONF_STATION_NUMBER]
                measuring_station, errors = await get_by_station_number(
                    waqi_client, abs(station_number)
                )
                if not measuring_station:
                    measuring_station, _ = await get_by_station_number(
                        waqi_client,
                        abs(station_number) - station_number - station_number,
                    )
                if measuring_station:
                    return await self._async_create_entry(measuring_station)
        return self.async_show_form(
            step_id=CONF_STATION_NUMBER,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STATION_NUMBER,
                    ): int,
                }
            ),
            errors=errors,
        )

    async def _async_create_entry(
        self, measuring_station: WAQIAirQuality
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(str(measuring_station.station_id))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=measuring_station.city.name,
            data={
                CONF_API_KEY: self.data[CONF_API_KEY],
                CONF_STATION_NUMBER: measuring_station.station_id,
            },
        )

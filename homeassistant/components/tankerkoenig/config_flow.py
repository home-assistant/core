"""Config flow for Tankerkoenig."""
from __future__ import annotations

from typing import Any

from pytankerkoenig import customException, getNearbyStations
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
    LENGTH_KILOMETERS,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
)

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DEFAULT_RADIUS, DOMAIN, FUEL_TYPES


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Init the FlowHandler."""
        super().__init__()
        self._data: dict[str, Any] = {}
        self._stations: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import YAML configuration."""
        await self.async_set_unique_id(
            f"{config[CONF_LOCATION][CONF_LATITUDE]}_{config[CONF_LOCATION][CONF_LONGITUDE]}"
        )
        self._abort_if_unique_id_configured()

        selected_station_ids: list[str] = []
        # add all nearby stations
        nearby_stations = await self._get_nearby_stations(config)
        for station in nearby_stations.get("stations", []):
            selected_station_ids.append(station["id"])

        # add all manual added stations
        for station_id in config[CONF_STATIONS]:
            selected_station_ids.append(station_id)

        return self._create_entry(
            data={
                CONF_NAME: "Home",
                CONF_API_KEY: config[CONF_API_KEY],
                CONF_FUEL_TYPES: config[CONF_FUEL_TYPES],
                CONF_LOCATION: config[CONF_LOCATION],
                CONF_RADIUS: config[CONF_RADIUS],
                CONF_STATIONS: selected_station_ids,
            },
            options={
                CONF_SHOW_ON_MAP: config[CONF_SHOW_ON_MAP],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if not user_input:
            return self._show_form_user()

        await self.async_set_unique_id(
            f"{user_input[CONF_LOCATION][CONF_LATITUDE]}_{user_input[CONF_LOCATION][CONF_LONGITUDE]}"
        )
        self._abort_if_unique_id_configured()

        data = await self._get_nearby_stations(user_input)
        if not data.get("ok"):
            return self._show_form_user(
                user_input, errors={CONF_API_KEY: "invalid_auth"}
            )
        if stations := data.get("stations"):
            for station in stations:
                self._stations[
                    station["id"]
                ] = f"{station['brand']} {station['street']} {station['houseNumber']} - ({station['dist']}km)"

        else:
            return self._show_form_user(user_input, errors={CONF_RADIUS: "no_stations"})

        self._data = user_input

        return await self.async_step_select_station()

    async def async_step_select_station(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step select_station of a flow initialized by the user."""
        if not user_input:
            return self.async_show_form(
                step_id="select_station",
                description_placeholders={"stations_count": len(self._stations)},
                data_schema=vol.Schema(
                    {vol.Required(CONF_STATIONS): cv.multi_select(self._stations)}
                ),
            )

        return self._create_entry(
            data={**self._data, **user_input},
            options={CONF_SHOW_ON_MAP: True},
        )

    def _show_form_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, "")
                    ): cv.string,
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                    ): cv.string,
                    vol.Required(
                        CONF_FUEL_TYPES,
                        default=user_input.get(CONF_FUEL_TYPES, list(FUEL_TYPES)),
                    ): cv.multi_select(FUEL_TYPES),
                    vol.Required(
                        CONF_LOCATION,
                        default=user_input.get(
                            CONF_LOCATION,
                            {
                                "latitude": self.hass.config.latitude,
                                "longitude": self.hass.config.longitude,
                            },
                        ),
                    ): LocationSelector(),
                    vol.Required(
                        CONF_RADIUS, default=user_input.get(CONF_RADIUS, DEFAULT_RADIUS)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1,
                            max=25,
                            step=0.1,
                            unit_of_measurement=LENGTH_KILOMETERS,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    def _create_entry(
        self, data: dict[str, Any], options: dict[str, Any]
    ) -> FlowResult:
        return self.async_create_entry(
            title=data[CONF_NAME],
            data=data,
            options=options,
        )

    async def _get_nearby_stations(self, data: dict[str, Any]) -> dict[str, Any]:
        """Fetch nearby stations."""
        try:
            return await self.hass.async_add_executor_job(
                getNearbyStations,
                data[CONF_API_KEY],
                data[CONF_LOCATION][CONF_LATITUDE],
                data[CONF_LOCATION][CONF_LONGITUDE],
                data[CONF_RADIUS],
                "all",
                "dist",
            )
        except customException as err:
            return {"ok": False, "message": err, "exception": True}


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SHOW_ON_MAP,
                        default=self.config_entry.options[CONF_SHOW_ON_MAP],
                    ): bool,
                }
            ),
        )

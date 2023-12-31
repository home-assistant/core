"""Config flow for the Ambient Weather Network integration."""
from __future__ import annotations

from typing import Any

from aioambient import OpenAPI
from geopy import Location, Nominatim
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import UnitOfLength
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import translation
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    API_STATION_INFO,
    API_STATION_MAC_ADDRESS,
    API_STATION_NAME,
    DOMAIN,
    ENTITY_MAC_ADDRESS,
    ENTITY_STATION_NAME,
    ENTITY_STATIONS,
    LOGGER,
)

CONFIG_STEP_USER = "user"
CONFIG_STEP_STATIONS = "stations"
CONFIG_STEP_STATION_NAME = "station_name"

CONFIG_LOCATION = "location"
CONFIG_LOCATION_LATITUDE = "latitude"
CONFIG_LOCATION_LONGITUDE = "longitude"
CONFIG_LOCATION_RADIUS = "radius"
CONFIG_LOCATION_RADIUS_DEFAULT = DistanceConverter.convert(
    0.5,
    UnitOfLength.MILES,
    UnitOfLength.METERS,
)

CONFIG_STATIONS = "stations"
CONFIG_STATION_NAME = "station_name"
CONFIG_STATION_NAME_SUFFIX = (
    f"component.{DOMAIN}.config.step.station_name.data.station_name_suffix"
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the Ambient Weather Network integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Construct the config flow."""

        self._longitude = 0.0
        self._latitude = 0.0
        self._radius = 0.0
        self._stations: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step to select the location."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._latitude = user_input[CONFIG_LOCATION][CONFIG_LOCATION_LATITUDE]
            self._longitude = user_input[CONFIG_LOCATION][CONFIG_LOCATION_LONGITUDE]
            self._radius = DistanceConverter.convert(
                user_input[CONFIG_LOCATION][CONFIG_LOCATION_RADIUS],
                UnitOfLength.METERS,
                UnitOfLength.MILES,
            )
            return await self.async_step_stations()

        schema: vol.Schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONFIG_LOCATION,
                    ): LocationSelector(LocationSelectorConfig(radius=True)),
                }
            ),
            {
                CONFIG_LOCATION: {
                    CONFIG_LOCATION_LATITUDE: self.hass.config.latitude,
                    CONFIG_LOCATION_LONGITUDE: self.hass.config.longitude,
                    CONFIG_LOCATION_RADIUS: CONFIG_LOCATION_RADIUS_DEFAULT,
                }
            },
        )

        return self.async_show_form(
            step_id=CONFIG_STEP_USER,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the second step to select the station."""

        errors: dict[str, str] = {}
        if user_input is not None:

            def parse_station(station: str) -> dict[str, str]:
                mac_address, station_name = station.split(",")
                return {
                    ENTITY_STATION_NAME: station_name,
                    ENTITY_MAC_ADDRESS: mac_address,
                }

            self._stations = list(map(parse_station, user_input[CONFIG_STATIONS]))
            if len(self._stations) == 0:
                return self.async_abort(reason="no_stations_selected")

            return await self.async_step_station_name()

        client: OpenAPI = OpenAPI()
        stations: list[dict[str, Any]] = await client.get_devices_by_location(
            self._latitude, self._longitude, radius=self._radius
        )

        if len(stations) == 0:
            return self.async_abort(reason="no_stations_found")

        options: list[SelectOptionDict] = list[SelectOptionDict]()
        for station in stations:
            station_name: str = station[API_STATION_INFO][API_STATION_NAME]
            option: SelectOptionDict = SelectOptionDict(
                label=f"{station_name}",
                value=f"{station[API_STATION_MAC_ADDRESS]},{station_name}",
            )
            options.append(option)

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONFIG_STATIONS, default=None): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                )
            }
        )

        return self.async_show_form(
            step_id=CONFIG_STEP_STATIONS,
            data_schema=schema,
            errors=errors,
        )

    async def suggest_virtual_station_name(self) -> str:
        """Suggest a name for a virtual station. The suggested name is composed of the city name and the word 'Weather Station'."""
        geolocator = Nominatim(user_agent="homeassistant", timeout=3)
        translations: dict[str, str] = await translation.async_get_translations(
            self.hass, self.hass.config.language, "config", {DOMAIN}
        )
        suffix = translations[CONFIG_STATION_NAME_SUFFIX]
        try:
            location: Location = await self.hass.async_add_executor_job(
                lambda: geolocator.reverse(
                    str(self._latitude) + "," + str(self._longitude)
                )
            )
            return str(location.raw["address"]["city"]) + " " + suffix
        except Exception:  # pylint: disable=broad-exception-caught
            LOGGER.warning("Failed to look up geo city name")
            return suffix

    async def async_step_station_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the third step to assign a station name."""

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONFIG_STATION_NAME] == "":
                return self.async_abort(reason="no_station_name_defined")

            await self.async_set_unique_id(user_input[CONFIG_STATION_NAME])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{user_input[CONFIG_STATION_NAME]}",
                data={
                    ENTITY_STATION_NAME: user_input[CONFIG_STATION_NAME],
                    ENTITY_STATIONS: self._stations,
                },
            )

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(
                    CONFIG_STATION_NAME,
                    default=self._stations[0][ENTITY_STATION_NAME]
                    if len(self._stations) == 1
                    else await self.suggest_virtual_station_name(),
                ): str
            }
        )

        return self.async_show_form(
            step_id=CONFIG_STEP_STATION_NAME,
            data_schema=schema,
            errors=errors,
        )

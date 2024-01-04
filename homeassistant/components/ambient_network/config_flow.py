"""Config flow for the Ambient Weather Network integration."""
from __future__ import annotations

from typing import Any

from aioambient import OpenAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import UnitOfLength
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    API_STATION_INFO,
    API_STATION_MAC_ADDRESS,
    API_STATION_NAME,
    DOMAIN,
    ENTITY_MAC_ADDRESS,
    ENTITY_STATION_NAME,
)

CONFIG_USER = "user"

CONFIG_LOCATION = "location"
CONFIG_LOCATION_LATITUDE = "latitude"
CONFIG_LOCATION_LONGITUDE = "longitude"
CONFIG_LOCATION_RADIUS = "radius"
CONFIG_LOCATION_RADIUS_DEFAULT = DistanceConverter.convert(
    0.5,
    UnitOfLength.MILES,
    UnitOfLength.METERS,
)

CONFIG_STATION = "station"
CONFIG_STATION_NAME = "station_name"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the Ambient Weather Network integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Construct the config flow."""

        self._longitude = 0.0
        self._latitude = 0.0
        self._radius = 0.0
        self._station: dict[str, str] = {}

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
            return await self.async_step_station()

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
            step_id=CONFIG_USER,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_station(
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

            self._station = parse_station(user_input[CONFIG_STATION])
            return await self.async_step_station_name()

        client: OpenAPI = OpenAPI()
        stations: list[dict[str, Any]] = await client.get_devices_by_location(
            self._latitude, self._longitude, radius=self._radius
        )

        if len(stations) == 0:
            return self.async_abort(reason="no_stations_found")

        options: list[SelectOptionDict] = list[SelectOptionDict]()
        for station in sorted(
            stations, key=lambda s: s[API_STATION_INFO][API_STATION_NAME]
        ):
            station_name: str = station[API_STATION_INFO][API_STATION_NAME]
            option: SelectOptionDict = SelectOptionDict(
                label=f"{station_name}",
                value=f"{station[API_STATION_MAC_ADDRESS]},{station_name}",
            )
            options.append(option)

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONFIG_STATION): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=False,
                    ),
                )
            }
        )

        return self.async_show_form(
            step_id=CONFIG_STATION,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_station_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the third step to assign a station name."""

        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONFIG_STATION_NAME]:
                return self.async_abort(reason="no_station_name_defined")

            await self.async_set_unique_id(self._station[ENTITY_MAC_ADDRESS])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{user_input[CONFIG_STATION_NAME]}",
                data={
                    ENTITY_STATION_NAME: user_input[CONFIG_STATION_NAME],
                    ENTITY_MAC_ADDRESS: self._station[ENTITY_MAC_ADDRESS],
                },
            )

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(
                    CONFIG_STATION_NAME,
                    default=self._station[ENTITY_STATION_NAME],
                ): str
            }
        )

        return self.async_show_form(
            step_id=CONFIG_STATION_NAME,
            data_schema=schema,
            errors=errors,
        )

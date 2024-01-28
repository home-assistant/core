"""Config flow for the Ambient Weather Network integration."""
from __future__ import annotations

from typing import Any

from aioambient import OpenAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_MAC,
    CONF_RADIUS,
    UnitOfLength,
)
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
    API_LAST_DATA,
    API_STATION_COORDS,
    API_STATION_INDOOR,
    API_STATION_INFO,
    API_STATION_LOCATION,
    API_STATION_MAC_ADDRESS,
    API_STATION_NAME,
    API_STATION_TYPE,
    DOMAIN,
)

CONF_USER = "user"
CONF_STATION = "station"

# One mile
CONF_RADIUS_DEFAULT = 1609.34


def get_station_name(station: dict[str, Any]) -> str:
    """Pick a station name.

    Station names can be empty, in which case we construct the name from
    the location and device type.
    """
    if name := station.get(API_STATION_INFO, {}).get(API_STATION_NAME):
        return str(name)
    location = (
        station.get(API_STATION_INFO, {})
        .get(API_STATION_COORDS, {})
        .get(API_STATION_LOCATION)
    )
    station_type = station.get(API_LAST_DATA, {}).get(API_STATION_TYPE)
    return f"{location}{'' if location is None or station_type is None else ' '}{station_type}"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the Ambient Weather Network integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Construct the config flow."""

        self._longitude = 0.0
        self._latitude = 0.0
        self._radius = 0.0

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle the initial step to select the location."""

        if user_input:
            self._latitude = user_input[CONF_LOCATION][CONF_LATITUDE]
            self._longitude = user_input[CONF_LOCATION][CONF_LONGITUDE]
            self._radius = user_input[CONF_LOCATION][CONF_RADIUS]
            return await self.async_step_station()

        schema: vol.Schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                    ): LocationSelector(LocationSelectorConfig(radius=True)),
                }
            ),
            {
                CONF_LOCATION: {
                    CONF_LATITUDE: self.hass.config.latitude
                    if not errors
                    else self._latitude,
                    CONF_LONGITUDE: self.hass.config.longitude
                    if not errors
                    else self._longitude,
                    CONF_RADIUS: CONF_RADIUS_DEFAULT if not errors else self._radius,
                }
            },
        )

        return self.async_show_form(
            step_id=CONF_USER, data_schema=schema, errors=errors if errors else {}
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the second step to select the station."""

        if user_input:
            mac_address, station_name = user_input[CONF_STATION].split(",")
            await self.async_set_unique_id(mac_address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=station_name,
                data={
                    CONF_MAC: mac_address,
                },
            )

        client: OpenAPI = OpenAPI()
        stations: list[dict[str, Any]] = await client.get_devices_by_location(
            self._latitude,
            self._longitude,
            radius=DistanceConverter.convert(
                self._radius,
                UnitOfLength.METERS,
                UnitOfLength.MILES,
            ),
        )

        # Filter out indoor stations
        stations = list(
            filter(
                lambda station: not station.get(API_STATION_INFO, {}).get(
                    API_STATION_INDOOR, False
                ),
                stations,
            )
        )

        if not stations:
            return await self.async_step_user(
                errors={"base": "no_stations_found"},
            )

        options: list[SelectOptionDict] = [
            SelectOptionDict(
                label=get_station_name(station),
                value=f"{station[API_STATION_MAC_ADDRESS]},{get_station_name(station)}",
            )
            for station in sorted(stations, key=get_station_name)
        ]

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONF_STATION): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=False,
                    ),
                )
            }
        )

        return self.async_show_form(
            step_id=CONF_STATION,
            data_schema=schema,
        )

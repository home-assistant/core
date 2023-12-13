"""Config flow for the Ambient Weather Network integration."""
from __future__ import annotations

import hashlib
import re
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
    SelectSelectorMode,
)
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    API_STATION_INFO,
    API_STATION_MAC_ADDRESS,
    API_STATION_NAME,
    DOMAIN,
    ENTITY_MAC_ADDRESS,
    ENTITY_MNEMONIC,
    ENTITY_NAME,
    ENTITY_STATIONS,
)

CONFIG_STEP_USER = "user"
CONFIG_STEP_STATIONS = "stations"
CONFIG_STEP_MNEMONIC = "mnemonic"

CONFIG_LOCATION = "location"
CONFIG_LOCATION_LATITUDE = "latitude"
CONFIG_LOCATION_LONGITUDE = "longitude"
CONFIG_LOCATION_RADIUS = "radius"
CONFIG_LOCATION_RADIUS_DEFAULT = 0.5  # in miles

CONFIG_STATIONS = "stations"
CONFIG_MNEMONIC = "mnemonic"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the Ambient Weather Network integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Construct the config flow."""

        super().__init__()
        self._longitude = 0.0
        self._latitude = 0.0
        self._radius = 0.0
        self._stations: list[dict[str, str]] = []

    def create_mnemonic(self, text: str) -> str:
        """Create a four-letter mnemonic from a text string."""

        # Split the text by spaces.
        words: list[str] = text.split()

        # Process each word.
        mnemonic: str = ""
        for word in words:
            # Use regular expression to split the word between uppercase and lowercase letters.
            parts: list[str] = re.findall(
                r"[a-z][a-z0-9\-]+|[A-Z][a-z0-9\-]+|[A-Z][A-Z0-9\-]+", word
            )

            for part in parts:
                match: re.Match | None = re.match(r"([a-zA-Z]+)[\-0-9]", part)
                if match is not None:
                    # Take all the letters preceding the dash or numbers.
                    mnemonic += match.group(1).upper()
                else:
                    # Take the first letter from each part.
                    mnemonic += part[0].upper()

        # Ensure the mnemonic is exactly four letters long.
        mnemonic = mnemonic[:4]

        return mnemonic

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
                    CONFIG_LOCATION_RADIUS: DistanceConverter.convert(
                        CONFIG_LOCATION_RADIUS_DEFAULT,
                        UnitOfLength.MILES,
                        UnitOfLength.METERS,
                    ),
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
                mac_address, mnemonic, name = station.split(",")
                return {
                    ENTITY_NAME: name,
                    ENTITY_MAC_ADDRESS: mac_address,
                    ENTITY_MNEMONIC: mnemonic,
                }

            self._stations = list(map(parse_station, user_input[CONFIG_STATIONS]))
            if len(self._stations) == 0:
                return self.async_abort(reason="no_stations_selected")

            return await self.async_step_mnemonic()

        client: OpenAPI = OpenAPI()
        stations: list[dict[str, Any]] = await client.get_devices_by_location(
            self._latitude, self._longitude, radius=self._radius
        )

        if len(stations) == 0:
            return self.async_abort(reason="no_stations_found")

        options: list[SelectOptionDict] = list[SelectOptionDict]()
        for station in stations:
            name: str = station[API_STATION_INFO][API_STATION_NAME]
            mnemonic: str = self.create_mnemonic(name)
            option: SelectOptionDict = SelectOptionDict(
                label=f"{name} ({mnemonic})",
                value=f"{station[API_STATION_MAC_ADDRESS]},{mnemonic},{name}",
            )
            options.append(option)

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONFIG_STATIONS): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id=CONFIG_STEP_STATIONS,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_mnemonic(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the third step to assign a mnemonic."""

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONFIG_MNEMONIC] == "":
                return self.async_abort(reason="no_mnemonic_defined")

            md5 = hashlib.md5(
                ",".join([s[ENTITY_MAC_ADDRESS] for s in self._stations]).encode()
            )

            await self.async_set_unique_id(md5.hexdigest())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{user_input[CONFIG_MNEMONIC]}",
                data={
                    ENTITY_MNEMONIC: user_input[CONFIG_MNEMONIC],
                    ENTITY_STATIONS: self._stations,
                },
            )

        schema: vol.Schema = vol.Schema(
            {
                vol.Required(
                    CONFIG_MNEMONIC, default=self._stations[0][ENTITY_MNEMONIC]
                ): str
            }
        )

        return self.async_show_form(
            step_id=CONFIG_STEP_MNEMONIC,
            data_schema=schema,
            errors=errors,
        )

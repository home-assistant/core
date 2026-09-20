"""Configure Xiaomi Weather from coordinates."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import Location, XiaomiLocationClient, XiaomiWeatherClient, XiaomiWeatherError
from .const import CONF_CITY_ID, DOMAIN


class XiaomiWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Resolve coordinates and validate weather before saving."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the location inputs and matches."""
        self._coordinates: dict[str, float] = {}
        self._locations: dict[str, Location] = {}
        self._location: Location

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Resolve a weather city from the supplied coordinates."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._coordinates = user_input
            client = XiaomiLocationClient(async_get_clientsession(self.hass))
            try:
                locations = await client.async_locate(
                    user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
                )
            except XiaomiWeatherError:
                errors["base"] = "lookup_failed"
            else:
                self._locations = {location.city_id: location for location in locations}
                if not locations:
                    errors["base"] = "city_not_found"
                elif len(locations) > 1:
                    return await self.async_step_city()
                else:
                    self._location = locations[0]
                    return await self.async_step_confirm()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_LATITUDE): cv.latitude,
                        probatio.Required(CONF_LONGITUDE): cv.longitude,
                    }
                ),
                self._coordinates
                or {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                },
            ),
            errors=errors,
        )

    async def async_step_city(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a city when the coordinates match multiple locations."""
        if user_input is not None:
            self._location = self._locations[user_input[CONF_CITY_ID]]
            return await self.async_step_confirm()
        options: list[SelectOptionDict] = [
            {
                "value": location.city_id,
                "label": (
                    f"{location.name} · {location.affiliation} ({location.city_id})"
                ),
            }
            for location in self._locations.values()
        ]
        return self.async_show_form(
            step_id="city",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_CITY_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Review the resolved location before validating weather and saving."""
        await self.async_set_unique_id(self._location.city_id)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await XiaomiWeatherClient(
                    async_get_clientsession(self.hass),
                    self._location.city_id,
                    self._coordinates[CONF_LATITUDE],
                    self._coordinates[CONF_LONGITUDE],
                ).async_get_weather()
            except XiaomiWeatherError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self._location.name,
                    data={
                        CONF_NAME: self._location.name,
                        CONF_CITY_ID: self._location.city_id,
                        **self._coordinates,
                    },
                )
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "city_name": self._location.name,
                "city_id": self._location.city_id,
                "latitude": str(self._coordinates[CONF_LATITUDE]),
                "longitude": str(self._coordinates[CONF_LONGITUDE]),
            },
            errors=errors,
        )

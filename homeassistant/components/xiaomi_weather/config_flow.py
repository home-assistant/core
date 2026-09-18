"""Source-first location setup with review and recoverable validation."""

import re
from typing import Any, Literal, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_ZONE
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    Location,
    XiaomiLocationClient,
    XiaomiWeatherClient,
    XiaomiWeatherError,
    number,
)
from .const import CONF_CITY_ID, DOMAIN

SOURCE_STEPS = ("zone", "search", "coordinates")
CITY_INPUT = probatio.All(str, probatio.Strip, probatio.Length(min=1, max=100))


class XiaomiWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Resolve a location, review it, then validate weather before saving."""

    VERSION = 1

    def __init__(self) -> None:
        """Keep drafts separate from persisted configuration."""
        self._source: Literal["zone", "search", "coordinates"] = "zone"
        self._input: dict[str, Any] = {}
        self._coordinates: dict[str, float] = {}
        self._locations: dict[str, Location] = {}
        self._resolved: dict[str, Any] = {}
        self._reconfigure = False
        self._zone_name: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one coordinate source instead of mixing competing fields."""
        await self.async_set_unique_id(None)
        self._input = {}
        self._coordinates = {}
        self._zone_name = None
        self._locations = {}
        self._resolved = {}
        return self.async_show_menu(
            step_id="reconfigure" if self._reconfigure else "user",
            menu_options=SOURCE_STEPS,
            description_placeholders={
                "city_id": self._get_reconfigure_entry().data[CONF_CITY_ID]
                if self._reconfigure
                else "",
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Keep existing identity but start with fresh location inputs."""
        self._reconfigure = True
        return await self.async_step_user()

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Use Home or another zone; city override is explicitly optional."""
        self._source = "zone"
        return await self._async_source_step(user_input)

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search a city; optional explicit coordinates replace its center."""
        self._source = "search"
        return await self._async_source_step(user_input)

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter coordinates; optionally choose a particular weather city."""
        self._source = "coordinates"
        return await self._async_source_step(user_input)

    def _show_source_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Only show fields relevant to this location source."""
        schema: dict[Any, Any]
        if self._source == "search":
            schema = {
                probatio.Required(CONF_CITY_ID): CITY_INPUT,
                probatio.Optional("coordinates"): section(
                    probatio.Schema(
                        {
                            probatio.Optional(CONF_LATITUDE): cv.latitude,
                            probatio.Optional(CONF_LONGITUDE): cv.longitude,
                        }
                    ),
                    {"collapsed": not bool(self._input.get("coordinates"))},
                ),
            }
        else:
            schema = (
                {
                    probatio.Required(CONF_ZONE, default="zone.home"): EntitySelector(
                        EntitySelectorConfig(domain="zone")
                    )
                }
                if self._source == "zone"
                else {
                    probatio.Required(CONF_LATITUDE): cv.latitude,
                    probatio.Required(CONF_LONGITUDE): cv.longitude,
                }
            )
            schema[probatio.Optional("advanced")] = section(
                probatio.Schema({probatio.Optional(CONF_CITY_ID): CITY_INPUT}),
                {"collapsed": not bool(self._input.get("advanced"))},
            )
        return self.async_show_form(
            step_id=self._source,
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(schema), self._input
            ),
            errors=errors,
        )

    async def _async_source_step(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Resolve missing fields while retaining the original form on failure."""
        if user_input is None:
            return self._show_source_form({})
        self._input = dict(user_input)
        self._locations = {}
        self._resolved = {}
        self._coordinates = {}
        self._zone_name = None
        if self._source == "zone":
            zone_id = user_input[CONF_ZONE]
            state = self.hass.states.get(zone_id)
            latitude = number(state.attributes.get(CONF_LATITUDE)) if state else None
            longitude = number(state.attributes.get(CONF_LONGITUDE)) if state else None
            if (
                not zone_id.startswith("zone.")
                or latitude is None
                or not -90 <= latitude <= 90
                or longitude is None
                or not -180 <= longitude <= 180
            ):
                return self._show_source_form({CONF_ZONE: "invalid_zone"})
            assert state is not None
            self._zone_name = state.name
            self._coordinates = {CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude}
        else:
            coordinates = (
                user_input.get("coordinates", {})
                if self._source == "search"
                else user_input
            )
            has_lat, has_lon = (
                CONF_LATITUDE in coordinates,
                CONF_LONGITUDE in coordinates,
            )
            if has_lat != has_lon:
                return self._show_source_form({"base": "coordinates_required"})
            if has_lat:
                self._coordinates = {
                    CONF_LATITUDE: coordinates[CONF_LATITUDE],
                    CONF_LONGITUDE: coordinates[CONF_LONGITUDE],
                }
        city = (
            user_input[CONF_CITY_ID]
            if self._source == "search"
            else user_input.get("advanced", {}).get(CONF_CITY_ID, "")
        )
        client = XiaomiLocationClient(async_get_clientsession(self.hass))
        try:
            if not city:
                locations = await client.async_locate(
                    self._coordinates[CONF_LATITUDE], self._coordinates[CONF_LONGITUDE]
                )
            elif re.fullmatch(r"(?:weathercn:)?101[0-9]{6}", city):
                locations = await client.async_city(city.removeprefix("weathercn:"))
            elif city.isdecimal() or city.startswith("weathercn:"):
                return self._show_source_form({"base": "invalid_city_id"})
            else:
                locations = await client.async_search(city)
        except XiaomiWeatherError:
            return self._show_source_form({"base": "lookup_failed"})
        self._locations = {location.city_id: location for location in locations}
        if not self._locations:
            return self._show_source_form({"base": "city_not_found"})
        return await self.async_step_city()

    async def async_step_city(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a labelled result without another lookup request."""
        if user_input is not None:
            return await self._async_select_location(
                self._locations[user_input[CONF_CITY_ID]]
            )
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

    async def _async_select_location(self, location: Location) -> ConfigFlowResult:
        """Keep entity identity stable and prepare an uncommitted review draft."""
        entry = self._get_reconfigure_entry() if self._reconfigure else None
        if entry and entry.unique_id != location.city_id:
            return self._show_source_form({"base": "different_city"})
        self._resolved = {
            CONF_NAME: self._zone_name or (entry.title if entry else location.name),
            CONF_CITY_ID: location.city_id,
            CONF_LATITUDE: self._coordinates.get(CONF_LATITUDE, location.latitude),
            CONF_LONGITUDE: self._coordinates.get(CONF_LONGITUDE, location.longitude),
        }
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Review before saving; failed weather validation stays on this screen."""
        if user_input is not None and user_input.get("edit_location"):
            return await self.async_step_user()
        entry = self._get_reconfigure_entry() if self._reconfigure else None
        await self.async_set_unique_id(self._resolved[CONF_CITY_ID])
        if not entry:
            self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await XiaomiWeatherClient(
                    async_get_clientsession(self.hass),
                    self._resolved[CONF_CITY_ID],
                    self._resolved[CONF_LATITUDE],
                    self._resolved[CONF_LONGITUDE],
                ).async_get_weather()
            except XiaomiWeatherError:
                errors["base"] = "cannot_connect"
            else:
                if entry:
                    return self.async_update_reload_and_abort(
                        entry,
                        data=dict(self._resolved),
                        title=self._resolved[CONF_NAME],
                    )
                return self.async_create_entry(
                    title=self._resolved[CONF_NAME], data=dict(self._resolved)
                )
        location = self._locations[self._resolved[CONF_CITY_ID]]
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "city_name": location.name,
                "city_id": location.city_id,
                "latitude": str(self._resolved[CONF_LATITUDE]),
                "longitude": str(self._resolved[CONF_LONGITUDE]),
            },
            data_schema=probatio.Schema(
                {
                    probatio.Optional("edit_location", default=False): bool,
                }
            ),
            errors=errors,
        )

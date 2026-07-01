"""Config flow for the OpenAQ integration."""

from dataclasses import dataclass
from functools import partial
import logging
from math import inf
from typing import Any, override

from openaq.core.responses import Location
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
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LOCATION_ID,
    DOMAIN,
    MAX_RADIUS,
    OPENAQ_API_EXCEPTIONS,
    OPENAQ_AUTH_EXCEPTIONS,
    OPENAQ_RATE_LIMIT_EXCEPTIONS,
    SUBENTRY_TYPE_LOCATION,
)
from .coordinator import async_create_openaq_client, normalize_parameter
from .sensor import SENSOR_DESCRIPTIONS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})
LOCATION_FETCH_LIMIT = 100
LOCATION_SEARCH_RADII = (5000, 10000, MAX_RADIUS)
MAX_LOCATION_OPTIONS = 10
PARAMETER_DISPLAY_CODES = {
    "pm1": "PM1",
    "pm10": "PM10",
    "pm25": "PM2.5",
    "nox": "NOx",
}


@dataclass(slots=True)
class OpenAQLocationFlowData:
    """OpenAQ location data stored during the subentry flow."""

    location_id: int
    title: str
    supported_parameters: tuple[str, ...] = ()
    distance: float | None = None

    @property
    def select_label(self) -> str:
        """Return a label for the location selector."""
        if not self.supported_parameters:
            return self.title

        parameter_codes = sorted(
            PARAMETER_DISPLAY_CODES.get(parameter, parameter.upper())
            for parameter in self.supported_parameters
        )
        label = f"{self.title} ({', '.join(parameter_codes)})"
        if self.distance is not None:
            label = f"{label} - {self.distance / 1000:.1f} km"
        return label


def _location_title(location: Location) -> str:
    """Return a display title for an OpenAQ location."""
    if location.locality and location.locality != location.name:
        return f"{location.name}, {location.locality}"
    return location.name


def _search_radii(max_radius: int) -> tuple[int, ...]:
    """Return progressive search radii capped by the selected maximum radius."""
    radii: list[int] = []
    for radius in LOCATION_SEARCH_RADII:
        search_radius = min(radius, max_radius)
        if search_radius not in radii:
            radii.append(search_radius)
        if search_radius == max_radius:
            break
    return tuple(radii)


def _supported_parameters(location: Location) -> tuple[str, ...]:
    """Return supported sensor parameters for an OpenAQ location."""
    parameters: set[str] = set()
    for sensor in location.sensors:
        parameter_name = normalize_parameter(sensor.parameter)
        if parameter_name in SENSOR_DESCRIPTIONS:
            parameters.add(parameter_name)
    return tuple(sorted(parameters))


def _location_sort_key(
    location: OpenAQLocationFlowData,
) -> tuple[float, int, str, int]:
    """Return the ranking key for an OpenAQ location."""
    return (
        location.distance if location.distance is not None else inf,
        -len(location.supported_parameters),
        location.title,
        location.location_id,
    )


def _location_from_result(location: Location) -> OpenAQLocationFlowData | None:
    """Return flow data for a useful OpenAQ location result."""
    supported_parameters = _supported_parameters(location)
    if not supported_parameters:
        return None

    return OpenAQLocationFlowData(
        location_id=location.id,
        title=_location_title(location),
        supported_parameters=supported_parameters,
        distance=location.distance,
    )


def _is_location_configured(hass: HomeAssistant, location_id: int) -> bool:
    """Return whether an OpenAQ location is already configured."""
    unique_id = str(location_id)
    for entry in hass.config_entries.async_entries(DOMAIN):
        for subentry in entry.subentries.values():
            if subentry.unique_id == unique_id:
                return True
    return False


class OpenAQConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAQ."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_LOCATION: OpenAQLocationSubentryFlow}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            try:
                client = await async_create_openaq_client(
                    self.hass, user_input[CONF_API_KEY]
                )
                try:
                    await self.hass.async_add_executor_job(
                        partial(client.parameters.list, limit=1)
                    )
                finally:
                    await self.hass.async_add_executor_job(client.close)
            except OPENAQ_AUTH_EXCEPTIONS:
                errors["base"] = "invalid_auth"
            except OPENAQ_RATE_LIMIT_EXCEPTIONS:
                errors["base"] = "rate_limited"
            except OPENAQ_API_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="OpenAQ",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class OpenAQLocationSubentryFlow(ConfigSubentryFlow):
    """Handle an OpenAQ location subentry flow."""

    _locations: dict[str, OpenAQLocationFlowData]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Find OpenAQ locations near a map point."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected_location = user_input[CONF_LOCATION]
            coordinates = (
                selected_location[CONF_LATITUDE],
                selected_location[CONF_LONGITUDE],
            )
            max_radius = max(
                1,
                min(
                    int(selected_location.get(CONF_RADIUS, MAX_RADIUS)),
                    MAX_RADIUS,
                ),
            )
            client = await async_create_openaq_client(
                self.hass, self._get_entry().data[CONF_API_KEY]
            )
            try:
                locations: dict[int, OpenAQLocationFlowData] = {}
                for radius in _search_radii(max_radius):
                    response = await self.hass.async_add_executor_job(
                        partial(
                            client.locations.list,
                            coordinates=coordinates,
                            radius=radius,
                            limit=LOCATION_FETCH_LIMIT,
                        )
                    )
                    for result_location in response.results:
                        location_data = _location_from_result(result_location)
                        if location_data is None or _is_location_configured(
                            self.hass, location_data.location_id
                        ):
                            continue
                        locations.setdefault(location_data.location_id, location_data)
            except OPENAQ_AUTH_EXCEPTIONS:
                errors["base"] = "invalid_auth"
            except OPENAQ_RATE_LIMIT_EXCEPTIONS:
                errors["base"] = "rate_limited"
            except OPENAQ_API_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._locations = {
                    str(location.location_id): location
                    for location in sorted(locations.values(), key=_location_sort_key)[
                        :MAX_LOCATION_OPTIONS
                    ]
                }
                if not self._locations:
                    errors["base"] = "no_locations_found"
                else:
                    return await self.async_step_select()
            finally:
                await self.hass.async_add_executor_job(client.close)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=True)
                        ),
                    }
                ),
                {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                        CONF_RADIUS: MAX_RADIUS,
                    }
                },
            ),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select one of the found OpenAQ locations."""
        if user_input is not None:
            return self._async_create_location_entry(
                self._locations[user_input[CONF_LOCATION_ID]]
            )

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=location_id, label=location.select_label
                                )
                                for location_id, location in self._locations.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    def _async_create_location_entry(
        self, location: OpenAQLocationFlowData
    ) -> SubentryFlowResult:
        """Create an OpenAQ location subentry."""
        if _is_location_configured(self.hass, location.location_id):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=location.title,
            data={CONF_LOCATION_ID: location.location_id},
            unique_id=str(location.location_id),
        )

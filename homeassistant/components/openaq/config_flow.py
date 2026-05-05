"""Config flow for the OpenAQ integration."""

from dataclasses import dataclass
import logging
from math import inf
from typing import Any

from openaq import (
    ApiKeyMissingError,
    AsyncOpenAQ,
    BadGatewayError,
    BadRequestError,
    ForbiddenError,
    GatewayTimeoutError,
    HTTPRateLimitError,
    NotAuthorizedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    TimeoutError as OpenAQTimeoutError,
    ValidationError,
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LIMIT,
    CONF_LOCATION_ID,
    CONF_RADIUS,
    DEFAULT_LOCATION_LIMIT,
    DEFAULT_RADIUS,
    DOMAIN,
    MAX_RADIUS,
    SUBENTRY_TYPE_LOCATION,
)
from .coordinator import (
    async_create_openaq_client,
    get_openaq_value,
    normalize_parameter,
)
from .sensor import SENSOR_DESCRIPTIONS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})
LOCATION_SEARCH_RADII = (5000, 10000, MAX_RADIUS)
MAX_LOCATION_OPTIONS = 5
SENSOR_DISPLAY_NAMES = {
    "bc": "Black carbon",
    "co": "Carbon monoxide",
    "co2": "Carbon dioxide",
    "no": "Nitrogen monoxide",
    "no2": "Nitrogen dioxide",
    "nox": "Nitrogen oxides",
    "o3": "Ozone",
    "pm1": "PM1",
    "pm10": "PM10",
    "pm25": "PM2.5",
    "so2": "Sulphur dioxide",
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

        sensor_names = sorted(
            SENSOR_DISPLAY_NAMES[parameter] for parameter in self.supported_parameters
        )
        sensor_count = len(sensor_names)
        sensor_word = "sensor" if sensor_count == 1 else "sensors"
        distance = "unknown distance"
        if self.distance is not None:
            distance = f"{self.distance / 1000:.1f} km"
        return (
            f"{self.title} - {sensor_count} {sensor_word}: "
            f"{', '.join(sensor_names)} - {distance}"
        )


async def _get_client(hass: HomeAssistant, api_key: str) -> AsyncOpenAQ:
    """Return an OpenAQ client."""
    return await async_create_openaq_client(hass, api_key)


async def validate_input(_hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = await _get_client(_hass, data[CONF_API_KEY])
    try:
        await client.parameters.list(limit=1)
    except (ApiKeyMissingError, ForbiddenError, NotAuthorizedError) as err:
        raise InvalidAuth from err
    except (HTTPRateLimitError, RateLimitError) as err:
        raise RateLimited from err
    except (
        BadGatewayError,
        BadRequestError,
        GatewayTimeoutError,
        NotFoundError,
        OpenAQTimeoutError,
        ServerError,
        ServiceUnavailableError,
        ValidationError,
    ) as err:
        raise CannotConnect from err
    finally:
        await client.close()


def _location_title(location: object) -> str:
    """Return a display title for an OpenAQ location."""
    name = get_openaq_value(location, "name")
    locality = get_openaq_value(location, "locality")
    if isinstance(locality, str) and locality and locality != name:
        return f"{name}, {locality}"
    return str(name)


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


def _supported_parameters(location: object) -> tuple[str, ...]:
    """Return supported sensor parameters for an OpenAQ location."""
    sensors = get_openaq_value(location, "sensors")
    if not isinstance(sensors, list):
        return ()

    parameters: set[str] = set()
    for sensor in sensors:
        parameter_name = normalize_parameter(get_openaq_value(sensor, "parameter"))
        if parameter_name in SENSOR_DESCRIPTIONS:
            parameters.add(parameter_name)
    return tuple(sorted(parameters))


def _location_distance(location: object) -> float | None:
    """Return the location distance in meters."""
    distance = get_openaq_value(location, "distance")
    if isinstance(distance, bool) or not isinstance(distance, (int, float)):
        return None
    return float(distance)


def _location_sort_key(
    location: OpenAQLocationFlowData,
) -> tuple[int, float, str, int]:
    """Return the ranking key for an OpenAQ location."""
    return (
        -len(location.supported_parameters),
        location.distance if location.distance is not None else inf,
        location.title,
        location.location_id,
    )


def _location_from_result(location: object) -> OpenAQLocationFlowData | None:
    """Return flow data for a useful OpenAQ location result."""
    location_id = get_openaq_value(location, "id")
    if not isinstance(location_id, int):
        return None

    supported_parameters = _supported_parameters(location)
    if not supported_parameters:
        return None

    return OpenAQLocationFlowData(
        location_id=location_id,
        title=_location_title(location),
        supported_parameters=supported_parameters,
        distance=_location_distance(location),
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
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_LOCATION: OpenAQLocationSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except RateLimited:
                errors["base"] = "rate_limited"
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
        """Handle adding an OpenAQ location."""
        return await self.async_step_map()

    async def async_step_map(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Find OpenAQ locations near a map point."""
        errors: dict[str, str] = {}
        if user_input is not None:
            coordinates = (
                user_input[CONF_LOCATION][CONF_LATITUDE],
                user_input[CONF_LOCATION][CONF_LONGITUDE],
            )
            client = await _get_client(self.hass, self._get_entry().data[CONF_API_KEY])
            try:
                locations: dict[int, OpenAQLocationFlowData] = {}
                for radius in _search_radii(user_input[CONF_RADIUS]):
                    response = await client.locations.list(
                        coordinates=coordinates,
                        radius=radius,
                        limit=user_input[CONF_LIMIT],
                    )
                    for location in response.results:
                        location_data = _location_from_result(location)
                        if location_data is None:
                            continue
                        locations.setdefault(location_data.location_id, location_data)
            except ApiKeyMissingError, ForbiddenError, NotAuthorizedError:
                errors["base"] = "invalid_auth"
            except HTTPRateLimitError, RateLimitError:
                errors["base"] = "rate_limited"
            except (
                BadGatewayError,
                BadRequestError,
                GatewayTimeoutError,
                NotFoundError,
                OpenAQTimeoutError,
                ServerError,
                ServiceUnavailableError,
                ValidationError,
            ):
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
                await client.close()

        return self.async_show_form(
            step_id="map",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=False)
                        ),
                        vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS): vol.All(
                            vol.Coerce(int), vol.Range(min=1, max=MAX_RADIUS)
                        ),
                        vol.Required(
                            CONF_LIMIT, default=DEFAULT_LOCATION_LIMIT
                        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class RateLimited(HomeAssistantError):
    """Error to indicate the API rate limit was exceeded."""

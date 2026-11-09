"""Config flow for the GeoSphere Austria Forecast integration."""

from http import HTTPStatus
import logging
from typing import Any, override

import probatio
from zamg import NwpClient, NwpForecast, ZamgApiError, ZamgNoDataError

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN, REQUEST_TIMEOUT, SUBENTRY_TYPE_LOCATION

_LOGGER = logging.getLogger(__name__)


def _home_location(hass: HomeAssistant) -> dict[str, float]:
    """Return the Home Assistant home location as selector value."""
    return {CONF_LATITUDE: hass.config.latitude, CONF_LONGITUDE: hass.config.longitude}


async def _async_check_location(
    hass: HomeAssistant, location: dict[str, float], errors: dict[str, str]
) -> NwpForecast | None:
    """Fetch a forecast for a location, adding a form error if that fails."""
    client = NwpClient(session=async_get_clientsession(hass))
    client.request_timeout = REQUEST_TIMEOUT
    try:
        return await client.get_forecast(
            latitude=location[CONF_LATITUDE], longitude=location[CONF_LONGITUDE]
        )
    except ZamgApiError as err:
        if err.status_code == HTTPStatus.BAD_REQUEST:
            errors["base"] = "outside_coverage"
        else:
            errors["base"] = "cannot_connect"
    except ZamgNoDataError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error fetching a GeoSphere Austria forecast")
        errors["base"] = "unknown"
    return None


def _grid_point_id(forecast: NwpForecast) -> str:
    """Return an ID for the model grid point a location resolves to."""
    return f"{forecast.resolved_latitude:.4f}-{forecast.resolved_longitude:.4f}"


def _first_location_title(hass: HomeAssistant, location: dict[str, float]) -> str:
    """Return the home name for the home location, else the coordinates."""
    if location == _home_location(hass):
        return hass.config.location_name
    return f"{location[CONF_LATITUDE]:.2f}, {location[CONF_LONGITUDE]:.2f}"


def _location_data(location: dict[str, float]) -> dict[str, float]:
    """Return the subentry data for a selected location."""
    return {
        CONF_LATITUDE: location[CONF_LATITUDE],
        CONF_LONGITUDE: location[CONF_LONGITUDE],
    }


class GeoSphereAustriaForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GeoSphere Austria Forecast."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the integration with a first location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                forecast := await _async_check_location(
                    self.hass, user_input[CONF_LOCATION], errors
                )
            ) is not None:
                return self.async_create_entry(
                    title="GeoSphere Austria Forecast",
                    data={},
                    subentries=[
                        ConfigSubentryData(
                            data=_location_data(user_input[CONF_LOCATION]),
                            subentry_type=SUBENTRY_TYPE_LOCATION,
                            title=_first_location_title(
                                self.hass, user_input[CONF_LOCATION]
                            ),
                            unique_id=_grid_point_id(forecast),
                        )
                    ],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_LOCATION, default=_home_location(self.hass)
                        ): LocationSelector(LocationSelectorConfig(radius=False))
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types this integration supports."""
        return {SUBENTRY_TYPE_LOCATION: LocationSubentryFlowHandler}


class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a location."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Ask for a location and its name."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                forecast := await _async_check_location(
                    self.hass, user_input[CONF_LOCATION], errors
                )
            ) is not None:
                unique_id = _grid_point_id(forecast)
                if any(
                    subentry.unique_id == unique_id
                    for subentry in self._get_entry().get_subentries_of_type(
                        SUBENTRY_TYPE_LOCATION
                    )
                ):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=_location_data(user_input[CONF_LOCATION]),
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_NAME, default=self.hass.config.location_name
                        ): str,
                        probatio.Required(
                            CONF_LOCATION, default=_home_location(self.hass)
                        ): LocationSelector(LocationSelectorConfig(radius=False)),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

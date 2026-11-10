"""Config flow for the GeoSphere Austria Forecast integration."""

from http import HTTPStatus
import logging
from typing import Any, override

import probatio
from zamg import NwpClient, NwpForecast, ZamgApiError, ZamgNoDataError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN, REQUEST_TIMEOUT

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


def _location_title(hass: HomeAssistant, location: dict[str, float]) -> str:
    """Return the home name for the home location, else the coordinates."""
    if location == _home_location(hass):
        return hass.config.location_name
    return f"{location[CONF_LATITUDE]:.2f}, {location[CONF_LONGITUDE]:.2f}"


class GeoSphereAustriaForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GeoSphere Austria Forecast."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            if (
                forecast := await _async_check_location(self.hass, location, errors)
            ) is not None:
                await self.async_set_unique_id(_grid_point_id(forecast))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_location_title(self.hass, location),
                    data={
                        CONF_LATITUDE: location[CONF_LATITUDE],
                        CONF_LONGITUDE: location[CONF_LONGITUDE],
                    },
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

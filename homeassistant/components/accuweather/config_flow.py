"""Adds config flow for AccuWeather."""

from asyncio import timeout
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, override

from accuweather import AccuWeather
from accuweather.exceptions import ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN
from .coordinator import AccuWeatherConfigEntry


class AccuWeatherFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for AccuWeather."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            websession = async_get_clientsession(self.hass)
            try:
                async with timeout(10):
                    accuweather = AccuWeather(
                        user_input[CONF_API_KEY],
                        websession,
                        latitude=user_input[CONF_LOCATION][CONF_LATITUDE],
                        longitude=user_input[CONF_LOCATION][CONF_LONGITUDE],
                    )
                    await accuweather.async_get_location()
            except ApiError, ClientConnectorError, TimeoutError, ClientError:
                errors["base"] = "cannot_connect"
            except InvalidApiKeyError:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RequestsExceededError:
                errors[CONF_API_KEY] = "requests_exceeded"
            else:
                await self.async_set_unique_id(
                    accuweather.location_key, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                if TYPE_CHECKING:
                    assert accuweather.location_name is not None

                location: dict[str, Any] = user_input.pop(CONF_LOCATION)
                return self.async_create_entry(
                    title=accuweather.location_name, data={**user_input, **location}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                        probatio.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=False)
                        ),
                    }
                ),
                user_input
                or {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        return await self._async_update_api_key(
            "reauth_confirm", self._get_reauth_entry(), user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self._async_update_api_key(
            "reconfigure", self._get_reconfigure_entry(), user_input
        )

    async def _async_update_api_key(
        self,
        step_id: str,
        entry: AccuWeatherConfigEntry,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate a new API key against the entry's location and update the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            websession = async_get_clientsession(self.hass)
            try:
                async with timeout(10):
                    accuweather = AccuWeather(
                        user_input[CONF_API_KEY],
                        websession,
                        latitude=entry.data[CONF_LATITUDE],
                        longitude=entry.data[CONF_LONGITUDE],
                    )
                    await accuweather.async_get_location()
            except ApiError, ClientConnectorError, TimeoutError, ClientError:
                errors["base"] = "cannot_connect"
            except InvalidApiKeyError:
                errors["base"] = "invalid_api_key"
            except RequestsExceededError:
                errors["base"] = "requests_exceeded"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            errors=errors,
        )

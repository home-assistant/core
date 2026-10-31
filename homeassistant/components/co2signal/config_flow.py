"""Config flow for Co2signal integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aioelectricitymaps import (
    ElectricityMaps,
    ElectricityMapsInvalidTokenError,
    ElectricityMapsNoDataError,
)
import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COUNTRY_CODE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN
from .helpers import fetch_latest_carbon_intensity
from .util import get_extra_name

TYPE_USE_HOME = "use_home_location"
TYPE_SPECIFY_COORDINATES = "specify_coordinates"
TYPE_SPECIFY_COUNTRY = "specify_country_code"

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_PLACEHOLDER = {
    "register_link": "https://app.electricitymaps.com/home-assistant",
}

LOCATION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        translation_key="location",
        mode=SelectSelectorMode.LIST,
        options=[
            TYPE_USE_HOME,
            TYPE_SPECIFY_COORDINATES,
            TYPE_SPECIFY_COUNTRY,
        ],
    )
)


class ElectricityMapsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Co2signal."""

    VERSION = 1
    _data: dict | None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = probatio.Schema(
            {
                probatio.Required("location"): LOCATION_SELECTOR,
                probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                description_placeholders=DESCRIPTION_PLACEHOLDER,
            )

        return await self._async_handle_location(
            "user", data_schema, user_input["location"], user_input[CONF_API_KEY]
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the location."""
        entry_data = self._get_reconfigure_entry().data
        data_schema = probatio.Schema(
            {probatio.Required("location"): LOCATION_SELECTOR}
        )

        if user_input is None:
            location_type = TYPE_USE_HOME
            if CONF_COUNTRY_CODE in entry_data:
                location_type = TYPE_SPECIFY_COUNTRY
            elif CONF_LATITUDE in entry_data:
                location_type = TYPE_SPECIFY_COORDINATES
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    data_schema, {"location": location_type}
                ),
            )

        return await self._async_handle_location(
            "reconfigure",
            data_schema,
            user_input["location"],
            entry_data[CONF_API_KEY],
        )

    async def _async_handle_location(
        self,
        step_id: str,
        data_schema: probatio.Schema,
        location_type: str,
        api_key: str,
    ) -> ConfigFlowResult:
        """Continue with the step for the selected location type."""
        data = {CONF_API_KEY: api_key}

        if location_type == TYPE_SPECIFY_COORDINATES:
            self._data = data
            return await self.async_step_coordinates()

        if location_type == TYPE_SPECIFY_COUNTRY:
            self._data = data
            return await self.async_step_country()

        return await self._validate_and_create(step_id, data_schema, data)

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate coordinates."""
        data_schema = self.add_suggested_values_to_schema(
            probatio.Schema(
                {
                    probatio.Required(CONF_LOCATION): LocationSelector(
                        LocationSelectorConfig(radius=False)
                    ),
                }
            ),
            user_input or {CONF_LOCATION: self._suggested_coordinates()},
        )
        if user_input is None:
            return self.async_show_form(step_id="coordinates", data_schema=data_schema)

        assert self._data is not None

        return await self._validate_and_create(
            "coordinates", data_schema, {**self._data, **user_input[CONF_LOCATION]}
        )

    async def async_step_country(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate country."""
        data_schema = probatio.Schema(
            {
                probatio.Required(CONF_COUNTRY_CODE): cv.string,
            }
        )
        if self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                data_schema, user_input or self._get_reconfigure_entry().data
            )
        if user_input is None:
            return self.async_show_form(step_id="country", data_schema=data_schema)

        assert self._data is not None

        return await self._validate_and_create(
            "country", data_schema, {**self._data, **user_input}
        )

    def _suggested_coordinates(self) -> dict[str, float]:
        """Return the coordinates to prefill the coordinates step with."""
        if self.source == SOURCE_RECONFIGURE:
            entry_data = self._get_reconfigure_entry().data
            if CONF_LATITUDE in entry_data:
                return {
                    CONF_LATITUDE: entry_data[CONF_LATITUDE],
                    CONF_LONGITUDE: entry_data[CONF_LONGITUDE],
                }
        return {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the reauth step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth step."""
        data_schema = probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
            }
        )
        return await self._validate_and_create(
            "reauth_confirm", data_schema, user_input
        )

    async def _validate_and_create(
        self, step_id: str, data_schema: probatio.Schema, data: Mapping[str, Any] | None
    ) -> ConfigFlowResult:
        """Validate data and show form if it is invalid."""
        errors: dict[str, str] = {}

        if data:
            session = async_get_clientsession(self.hass)
            em = ElectricityMaps(token=data[CONF_API_KEY], session=session)

            try:
                await fetch_latest_carbon_intensity(self.hass, em, data)
            except ElectricityMapsInvalidTokenError:
                errors["base"] = "invalid_auth"
            except ElectricityMapsNoDataError:
                errors["base"] = "no_data"
            except Exception:
                _LOGGER.exception("Unexpected error occurred while checking API key")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={CONF_API_KEY: data[CONF_API_KEY]},
                    )
                if self.source == SOURCE_RECONFIGURE:
                    # Replace the data so keys of the previous location type are dropped
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data=data
                    )

                return self.async_create_entry(
                    title=get_extra_name(data) or "Electricity Maps",
                    data=data,
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDER,
        )

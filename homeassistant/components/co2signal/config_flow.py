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
    CONF_LONGITUDE,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
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

LOCATION_SCHEMA = probatio.Schema(
    {
        probatio.Required("location"): SelectSelector(
            SelectSelectorConfig(
                translation_key="location",
                mode=SelectSelectorMode.LIST,
                options=[
                    TYPE_USE_HOME,
                    TYPE_SPECIFY_COORDINATES,
                    TYPE_SPECIFY_COUNTRY,
                ],
            )
        ),
        probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
    }
)


def _get_location_type(data: Mapping[str, Any]) -> str:
    """Return the location type of the config entry data."""
    if CONF_COUNTRY_CODE in data:
        return TYPE_SPECIFY_COUNTRY
    if CONF_LATITUDE in data:
        return TYPE_SPECIFY_COORDINATES
    return TYPE_USE_HOME


class ElectricityMapsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Co2signal."""

    VERSION = 1
    _data: dict | None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=LOCATION_SCHEMA,
                description_placeholders=DESCRIPTION_PLACEHOLDER,
            )

        return await self._async_handle_location("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the location and API key."""
        if user_input is None:
            entry_data = self._get_reconfigure_entry().data
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    LOCATION_SCHEMA,
                    {**entry_data, "location": _get_location_type(entry_data)},
                ),
                description_placeholders=DESCRIPTION_PLACEHOLDER,
            )

        return await self._async_handle_location("reconfigure", user_input)

    async def _async_handle_location(
        self, step_id: str, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Continue to the step matching the selected location type."""
        data = {CONF_API_KEY: user_input[CONF_API_KEY]}

        if user_input["location"] == TYPE_SPECIFY_COORDINATES:
            self._data = data
            return await self.async_step_coordinates()

        if user_input["location"] == TYPE_SPECIFY_COUNTRY:
            self._data = data
            return await self.async_step_country()

        return await self._validate_and_create(step_id, LOCATION_SCHEMA, data)

    def _suggested_values(self) -> Mapping[str, Any] | None:
        """Return the current entry data when reconfiguring."""
        if self.source == SOURCE_RECONFIGURE:
            return self._get_reconfigure_entry().data
        return None

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate coordinates."""
        data_schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_LATITUDE,
                ): cv.latitude,
                probatio.Required(
                    CONF_LONGITUDE,
                ): cv.longitude,
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="coordinates",
                data_schema=self.add_suggested_values_to_schema(
                    data_schema, self._suggested_values()
                ),
            )

        assert self._data is not None

        return await self._validate_and_create(
            "coordinates", data_schema, {**self._data, **user_input}
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
        if user_input is None:
            return self.async_show_form(
                step_id="country",
                data_schema=self.add_suggested_values_to_schema(
                    data_schema, self._suggested_values()
                ),
            )

        assert self._data is not None

        return await self._validate_and_create(
            "country", data_schema, {**self._data, **user_input}
        )

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

                title = get_extra_name(data) or "Electricity Maps"
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), title=title, data=data
                    )

                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDER,
        )

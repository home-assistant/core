"""Config flow for Co2signal integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aioelectricitymaps import (
    ElectricityMaps,
    ElectricityMapsError,
    ElectricityMapsInvalidTokenError,
    ElectricityMapsNoDataError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COUNTRY_CODE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
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


class ElectricityMapsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Co2signal."""

    VERSION = 1
    _data: dict | None
    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(
            {
                vol.Required("location"): SelectSelector(
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
                vol.Required(CONF_API_KEY): cv.string,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        data = {CONF_API_KEY: user_input[CONF_API_KEY]}

        if user_input["location"] == TYPE_SPECIFY_COORDINATES:
            self._data = data
            return await self.async_step_coordinates()

        if user_input["location"] == TYPE_SPECIFY_COUNTRY:
            self._data = data
            return await self.async_step_country()

        return await self._validate_and_create("user", data_schema, data)

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate coordinates."""
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE,
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE,
                ): cv.longitude,
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="coordinates", data_schema=data_schema)

        assert self._data is not None

        return await self._validate_and_create(
            "coordinates", data_schema, {**self._data, **user_input}
        )

    async def async_step_country(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate country."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY_CODE): cv.string,
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="country", data_schema=data_schema)

        assert self._data is not None

        return await self._validate_and_create(
            "country", data_schema, {**self._data, **user_input}
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the reauth step."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
            }
        )
        return await self._validate_and_create("reauth", data_schema, entry_data)

    async def _validate_and_create(
        self, step_id: str, data_schema: vol.Schema, data: Mapping[str, Any]
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
            except ElectricityMapsError:
                errors["base"] = "unknown"
            else:
                if self._reauth_entry:
                    return self.async_update_reload_and_abort(
                        self._reauth_entry,
                        data={
                            CONF_API_KEY: data[CONF_API_KEY],
                        },
                    )

                return self.async_create_entry(
                    title=get_extra_name(data) or "CO2 Signal",
                    data=data,
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
        )

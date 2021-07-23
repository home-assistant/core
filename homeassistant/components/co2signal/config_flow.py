"""Config flow for Co2signal integration."""
from __future__ import annotations

import logging
from typing import Any

import CO2Signal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import CONF_COUNTRY_CODE, DOMAIN
from .util import get_extra_name

_LOGGER = logging.getLogger(__name__)

TYPE_USE_HOME = "Use home location"
TYPE_SPECIFY_COORDINATES = "Specify coordinates"
TYPE_SPECIFY_COUNTRY = "Specify country code"


def _get_entry_type(config: dict) -> str:
    """Get entry type from the configuration."""
    if CONF_LATITUDE in config:
        return TYPE_SPECIFY_COORDINATES

    if CONF_COUNTRY_CODE in config:
        return TYPE_SPECIFY_COUNTRY

    return TYPE_USE_HOME


def _validate_info(hass, config: dict) -> dict:
    """Validate the passed in info."""
    if CONF_COUNTRY_CODE in config:
        latitude = None
        longitude = None
    else:
        latitude = config.get(CONF_LATITUDE, hass.config.latitude)
        longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    try:
        data = CO2Signal.get_latest(
            config[CONF_API_KEY],
            config.get(CONF_COUNTRY_CODE),
            latitude,
            longitude,
            wait=False,
        )

    except ValueError as err:
        err_str = str(err)

        if "Invalid authentication credentials" in err_str:
            raise InvalidAuth from err
        if "API rate limit exceeded." in err_str:
            raise APIRatelimitExceeded from err

        _LOGGER.exception("Unexpected exception")
        raise UnknownError from err
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        raise UnknownError from err

    else:
        if data.get("status") != "ok":
            _LOGGER.exception("Unexpected response: %s", data)
            raise UnknownError

    return data


class CO2Error(HomeAssistantError):
    """Base error."""


class InvalidAuth(CO2Error):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(CO2Error):
    """Raised when the API rate limit is exceeded."""


class UnknownError(CO2Error):
    """Raised when an unknown error occurs."""


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Co2signal."""

    VERSION = 1
    _data: dict | None

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        data = {CONF_API_KEY: import_info[CONF_TOKEN]}

        if CONF_COUNTRY_CODE in import_info:
            data[CONF_COUNTRY_CODE] = import_info[CONF_COUNTRY_CODE]
            new_entry_type = TYPE_SPECIFY_COUNTRY
        elif (
            CONF_LATITUDE in import_info
            and import_info[CONF_LATITUDE] != self.hass.config.latitude
            and import_info[CONF_LONGITUDE] != self.hass.config.longitude
        ):
            data[CONF_LATITUDE] = import_info[CONF_LATITUDE]
            data[CONF_LONGITUDE] = import_info[CONF_LONGITUDE]
            new_entry_type = TYPE_SPECIFY_COORDINATES
        else:
            new_entry_type = TYPE_USE_HOME

        for entry in self._async_current_entries(include_ignore=False):

            if (cur_entry_type := _get_entry_type(entry.data)) != new_entry_type:
                continue

            if cur_entry_type == TYPE_USE_HOME and new_entry_type == TYPE_USE_HOME:
                return self.async_abort(reason="already_configured")

            if (
                cur_entry_type == TYPE_SPECIFY_COUNTRY
                and data[CONF_COUNTRY_CODE] == entry.data[CONF_COUNTRY_CODE]
            ):
                return self.async_abort(reason="already_configured")

            if (
                cur_entry_type == TYPE_SPECIFY_COORDINATES
                and data[CONF_LATITUDE] == entry.data[CONF_LATITUDE]
                and data[CONF_LONGITUDE] == entry.data[CONF_LONGITUDE]
            ):
                return self.async_abort(reason="already_configured")

        try:
            await self.hass.async_add_executor_job(_validate_info, self.hass, data)
        except CO2Error:
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=get_extra_name(self.hass, data) or "CO2 Signal", data=data
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(
            {
                vol.Required("location", default=TYPE_USE_HOME): vol.In(
                    (
                        TYPE_USE_HOME,
                        TYPE_SPECIFY_COORDINATES,
                        TYPE_SPECIFY_COUNTRY,
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
    ) -> FlowResult:
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
    ) -> FlowResult:
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

    async def _validate_and_create(
        self, step_id: str, data_schema: vol.Schema, data: dict
    ) -> FlowResult:
        """Validate data and show form if it is invalid."""
        errors: dict[str, str] = {}

        try:
            await self.hass.async_add_executor_job(_validate_info, self.hass, data)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except APIRatelimitExceeded:
            errors["base"] = "api_ratelimit"
        except UnknownError:
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=get_extra_name(self.hass, data) or "CO2 Signal",
                data=data,
            )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
        )

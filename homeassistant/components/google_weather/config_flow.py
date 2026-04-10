"""Config flow for the Google Weather integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from google_weather_api import GoogleWeatherApi, GoogleWeatherApiError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
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
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import CONF_REFERRER, DOMAIN, SECTION_API_KEY_OPTIONS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(SECTION_API_KEY_OPTIONS): section(
            vol.Schema({vol.Optional(CONF_REFERRER): str}), {"collapsed": True}
        ),
    }
)


async def _validate_input(
    user_input: dict[str, Any],
    api: GoogleWeatherApi,
    errors: dict[str, str],
    description_placeholders: dict[str, str],
) -> bool:
    try:
        await api.async_get_current_conditions(
            latitude=user_input[CONF_LOCATION][CONF_LATITUDE],
            longitude=user_input[CONF_LOCATION][CONF_LONGITUDE],
        )
    except GoogleWeatherApiError as err:
        errors["base"] = "cannot_connect"
        description_placeholders["error_message"] = str(err)
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        return True
    return False


def _get_location_schema(hass: HomeAssistant) -> vol.Schema:
    """Return the schema for a location with default values from the hass config."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=hass.config.location_name): str,
            vol.Required(
                CONF_LOCATION,
                default={
                    CONF_LATITUDE: hass.config.latitude,
                    CONF_LONGITUDE: hass.config.longitude,
                },
            ): LocationSelector(LocationSelectorConfig(radius=False)),
        }
    )


def _is_location_already_configured(
    hass: HomeAssistant,
    new_data: dict[str, float],
    epsilon: float = 1e-4,
    exclude_subentry_id: str | None = None,
) -> bool:
    """Check if the location is already configured."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        for subentry in entry.subentries.values():
            if exclude_subentry_id and subentry.subentry_id == exclude_subentry_id:
                continue
            # A more accurate way is to use the haversine formula, but for simplicity
            # we use a simple distance check. The epsilon value is small anyway.
            # This is mostly to capture cases where the user has slightly moved the location pin.
            if (
                abs(subentry.data[CONF_LATITUDE] - new_data[CONF_LATITUDE]) <= epsilon
                and abs(subentry.data[CONF_LONGITUDE] - new_data[CONF_LONGITUDE])
                <= epsilon
            ):
                return True
    return False


class GoogleWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Weather."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user, reauth or reconfigure."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {
            "api_key_url": "https://developers.google.com/maps/documentation/weather/get-api-key",
            "restricting_api_keys_url": "https://developers.google.com/maps/api-security-best-practices#restricting-api-keys",
        }
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            referrer = user_input.get(SECTION_API_KEY_OPTIONS, {}).get(CONF_REFERRER)
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
                entry = (
                    self._get_reauth_entry()
                    if self.source == SOURCE_REAUTH
                    else self._get_reconfigure_entry()
                )
                subentry = next(iter(entry.subentries.values()), None)
                if subentry:
                    latitude = subentry.data[CONF_LATITUDE]
                    longitude = subentry.data[CONF_LONGITUDE]
                else:
                    latitude = self.hass.config.latitude
                    longitude = self.hass.config.longitude
                validation_input = {
                    CONF_LOCATION: {CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude}
                }
            else:
                if _is_location_already_configured(
                    self.hass, user_input[CONF_LOCATION]
                ):
                    return self.async_abort(reason="already_configured")
                validation_input = user_input

            api = GoogleWeatherApi(
                session=async_get_clientsession(self.hass),
                api_key=api_key,
                referrer=referrer,
                language_code=self.hass.config.language,
            )
            if await _validate_input(
                validation_input, api, errors, description_placeholders
            ):
                data = {CONF_API_KEY: api_key, CONF_REFERRER: referrer}
                if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
                    return self.async_update_reload_and_abort(entry, data=data)

                return self.async_create_entry(
                    title="Google Weather",
                    data=data,
                    subentries=[
                        {
                            "subentry_type": "location",
                            "data": user_input[CONF_LOCATION],
                            "title": user_input[CONF_NAME],
                            "unique_id": None,
                        },
                    ],
                )

        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            entry = (
                self._get_reauth_entry()
                if self.source == SOURCE_REAUTH
                else self._get_reconfigure_entry()
            )
            if user_input is None:
                user_input = {
                    CONF_API_KEY: entry.data.get(CONF_API_KEY),
                    SECTION_API_KEY_OPTIONS: {
                        CONF_REFERRER: entry.data.get(CONF_REFERRER)
                    },
                }
            schema = STEP_USER_DATA_SCHEMA
        else:
            if user_input is None:
                user_input = {}
            schema_dict = STEP_USER_DATA_SCHEMA.schema.copy()
            schema_dict.update(_get_location_schema(self.hass).schema)
            schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        return await self.async_step_user(user_input)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"location": LocationSubentryFlowHandler}


class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for location."""

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == SOURCE_USER

    async def async_step_location(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Handle the location step."""
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            exclude_id = (
                None if self._is_new else self._get_reconfigure_subentry().subentry_id
            )
            if _is_location_already_configured(
                self.hass, user_input[CONF_LOCATION], exclude_subentry_id=exclude_id
            ):
                return self.async_abort(reason="already_configured")
            api: GoogleWeatherApi = self._get_entry().runtime_data.api
            if await _validate_input(user_input, api, errors, description_placeholders):
                if self._is_new:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input[CONF_LOCATION],
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    title=user_input[CONF_NAME],
                    data=user_input[CONF_LOCATION],
                )
        elif self._is_new:
            user_input = {}
        else:
            subentry = self._get_reconfigure_subentry()
            user_input = {
                CONF_NAME: subentry.title,
                CONF_LOCATION: dict(subentry.data),
            }

        return self.async_show_form(
            step_id="location",
            data_schema=self.add_suggested_values_to_schema(
                _get_location_schema(self.hass), user_input
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async_step_user = async_step_location
    async_step_reconfigure = async_step_location

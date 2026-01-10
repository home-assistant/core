"""Config flow for the Google Air Quality integration."""

from __future__ import annotations

import logging
from typing import Any

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.auth import Auth
from google_air_quality_api.exceptions import GoogleAirQualityApiError
from google_air_quality_api.mapping import AQICategoryMapping
import voluptuous as vol

from homeassistant.config_entries import (
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
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    CountrySelector,
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_REFERRER,
    CUSTOM_LOCAL_AQI_OPTIONS,
    DOMAIN,
    SECTION_API_KEY_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)
AIR_QUALITY_COVERAGE_URL = (
    "https://developers.google.com/maps/documentation/air-quality/coverage"
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(SECTION_API_KEY_OPTIONS): section(
            vol.Schema({vol.Optional(CONF_REFERRER): str}),
            SectionConfig(collapsed=True),
        ),
    }
)


async def _validate_input(
    user_input: dict[str, Any],
    api: GoogleAirQualityApi,
    errors: dict[str, str],
    description_placeholders: dict[str, str],
) -> bool:
    try:
        if user_input[CUSTOM_LOCAL_AQI_OPTIONS]["enable_custom_laqi"]:
            await api.async_get_current_conditions(
                lat=user_input[CONF_LOCATION][CONF_LATITUDE],
                lon=user_input[CONF_LOCATION][CONF_LONGITUDE],
                region_code=user_input[CUSTOM_LOCAL_AQI_OPTIONS]["country"],
                custom_local_aqi=user_input[CUSTOM_LOCAL_AQI_OPTIONS]["custom_laqi"],
            )
        if not user_input[CUSTOM_LOCAL_AQI_OPTIONS]["enable_custom_laqi"]:
            await api.async_get_current_conditions(
                lat=user_input[CONF_LOCATION][CONF_LATITUDE],
                lon=user_input[CONF_LOCATION][CONF_LONGITUDE],
            )
    except GoogleAirQualityApiError as err:
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
            vol.Optional(CUSTOM_LOCAL_AQI_OPTIONS): section(
                vol.Schema(
                    {
                        vol.Required("enable_custom_laqi", default=False): bool,
                        vol.Optional(
                            "country", default=hass.config.country
                        ): CountrySelector(),
                        vol.Optional("custom_laqi"): SelectSelector(
                            SelectSelectorConfig(
                                options=list(AQICategoryMapping.get_all_laq_indices()),
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
                SectionConfig(collapsed=True),
            ),
        }
    )


def _is_location_already_configured(
    hass: HomeAssistant, new_data: dict[str, float], epsilon: float = 1e-4
) -> bool:
    """Check if the location is already configured."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        for subentry in entry.subentries.values():
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


def _is_location_name_already_configured(hass: HomeAssistant, new_data: str) -> bool:
    """Check if the location name is already configured."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        for subentry in entry.subentries.values():
            if subentry.title.lower() == new_data.lower():
                return True
    return False


class GoogleAirQualityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google AirQuality."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {
            "api_key_url": "https://developers.google.com/maps/documentation/air-quality/get-api-key",
            "air_quality_coverage_url": AIR_QUALITY_COVERAGE_URL,
            "restricting_api_keys_url": "https://developers.google.com/maps/api-security-best-practices#restricting-api-keys",
        }
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            referrer = user_input.get(SECTION_API_KEY_OPTIONS, {}).get(CONF_REFERRER)
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            if _is_location_already_configured(self.hass, user_input[CONF_LOCATION]):
                return self.async_abort(reason="already_configured")
            session = async_get_clientsession(self.hass)
            referrer = user_input.get(SECTION_API_KEY_OPTIONS, {}).get(CONF_REFERRER)
            auth = Auth(session, user_input[CONF_API_KEY], referrer=referrer)
            api = GoogleAirQualityApi(auth)
            if await _validate_input(user_input, api, errors, description_placeholders):
                return self.async_create_entry(
                    title="Google Air Quality",
                    data={
                        CONF_API_KEY: api_key,
                        CONF_REFERRER: referrer,
                    },
                    subentries=[
                        {
                            "subentry_type": "location",
                            "data": user_input[CONF_LOCATION],
                            "title": user_input[CONF_NAME],
                            "unique_id": None,
                        },
                    ],
                )
        else:
            user_input = {}
        schema = STEP_USER_DATA_SCHEMA.schema.copy()
        schema.update(_get_location_schema(self.hass).schema)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), user_input
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"location": LocationSubentryFlowHandler}


class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for location."""

    async def async_step_location(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Handle the location step."""
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {
            "air_quality_coverage_url": AIR_QUALITY_COVERAGE_URL
        }
        if user_input is not None:
            _LOGGER.debug("User input: %s", user_input)
            if _is_location_already_configured(self.hass, user_input[CONF_LOCATION]):
                errors["base"] = "location_already_configured"
            if _is_location_name_already_configured(self.hass, user_input[CONF_NAME]):
                errors["base"] = "location_name_already_configured"
            api: GoogleAirQualityApi = self._get_entry().runtime_data.api
            if errors:
                return self.async_show_form(
                    step_id="location",
                    data_schema=self.add_suggested_values_to_schema(
                        _get_location_schema(self.hass), user_input
                    ),
                    errors=errors,
                    description_placeholders=description_placeholders,
                )
            if await _validate_input(user_input, api, errors, description_placeholders):
                data = user_input[CONF_LOCATION]
                data[CUSTOM_LOCAL_AQI_OPTIONS] = user_input[CUSTOM_LOCAL_AQI_OPTIONS]
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=data,
                )
        else:
            user_input = {}
        return self.async_show_form(
            step_id="location",
            data_schema=self.add_suggested_values_to_schema(
                _get_location_schema(self.hass), user_input
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async_step_user = async_step_location

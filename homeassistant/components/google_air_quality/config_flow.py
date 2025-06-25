"""Config flow for Google Air Quality."""

import logging
from typing import TYPE_CHECKING, Any

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.auth import Auth
from google_air_quality_api.exceptions import (
    GoogleAirQualityApiError,
    NoDataForLocationError,
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
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from .const import CONF_API_KEY_OPTIONS, CONF_REFERRER, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_INPUT: dict = {}

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_API_KEY_OPTIONS): section(
            vol.Schema(
                {
                    vol.Optional(
                        CONF_REFERRER,
                        default=USER_INPUT.get(CONF_REFERRER, vol.UNDEFINED),
                    ): str,
                }
            ),
            {"collapsed": True},
        ),
    },
)


class GoogleAirQaulityApiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow to handle Google Air Quality authentication."""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"location": LocationSubentryFlowHandler}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        user_input = user_input or {}
        if user_input:
            session = async_get_clientsession(self.hass)
            referrer = user_input.get(CONF_API_KEY_OPTIONS, {}).get(CONF_REFERRER)
            auth = Auth(session, user_input[CONF_API_KEY], referrer)
            client = GoogleAirQualityApi(auth)
            try:
                await client.async_air_quality(37.419734, -122.0827784)
            except GoogleAirQualityApiError as ex:
                _LOGGER.debug("Cannot fetch air quality data: %s", str(ex))
                return self.async_abort(
                    reason="unable_to_fetch",
                )
            except Exception:
                _LOGGER.exception("Unknown error occurred")
                return self.async_abort(reason="unknown")
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"API-Key: {'*' * (len(user_input[CONF_API_KEY]) - 3)}{user_input[CONF_API_KEY][-3:]}",
                data={CONF_REFERRER: referrer},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            description_placeholders={
                "more_info_url": "https://www.home-assistant.io/integrations/google_air_quality/"
            },
            errors=errors,
        )


class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a location."""

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """User flow to add a new location."""
        if user_input is not None:
            entry = self._get_entry()
            hass = self.hass
            session = async_get_clientsession(hass)
            if TYPE_CHECKING:
                assert entry.unique_id is not None
            auth = Auth(session, entry.unique_id)
            client = GoogleAirQualityApi(auth)
            location = user_input[CONF_LOCATION]
            lat = location[CONF_LATITUDE]
            lon = location[CONF_LONGITUDE]
            try:
                await client.async_air_quality(lat, lon)
            except NoDataForLocationError:
                return self._show_form_user(
                    user_input,
                    errors={"base": "no_data_for_location"},
                )
            except GoogleAirQualityApiError as ex:
                _LOGGER.debug("Cannot fetch air quality data: %s", str(ex))
                return self.async_abort(
                    reason="unable_to_fetch",
                )
            except Exception:
                _LOGGER.exception("Unknown error occurred")
                return self.async_abort(reason="unknown")

            unique_id = f"{lat}_{lon}"
            for entry in hass.config_entries.async_entries(DOMAIN):
                for subentry in entry.subentries.values():
                    if subentry.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")
            try:
                geo_data = await client.async_reverse_geocode(lat, lon)
                title = geo_data.results[0].formatted_address
                name = f"{lat}_{lon}"
                for component in geo_data.results[0].address_components or []:
                    _LOGGER.debug("component: %s", component)
                    if "route" in component.types:
                        name = component.short_text
                        break
            except (GoogleAirQualityApiError, ValueError, IndexError):
                _LOGGER.debug(
                    "Could not resolve address for %s,%s. Using coordinates instead",
                    lat,
                    lon,
                )
                title = f"Coordinates {lat}, {lon}"
                name = f"{lat}_{lon}"
            data = {
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: lon,
                CONF_NAME: name,
            }
            result = self.async_create_entry(
                title=title,
                data=data,
                unique_id=unique_id,
            )

            async def reload_later() -> None:
                """Reload the config entry after the subentry is created."""
                await hass.async_block_till_done()
                await self.hass.config_entries.async_reload(entry.entry_id)

            self.hass.async_create_task(reload_later())
            return result
        return self._show_form_user()

    def _show_form_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                        default=user_input.get(
                            CONF_LOCATION,
                            {
                                CONF_LATITUDE: self.hass.config.latitude,
                                CONF_LONGITUDE: self.hass.config.longitude,
                            },
                        ),
                    ): LocationSelector()
                }
            ),
            errors=errors,
        )

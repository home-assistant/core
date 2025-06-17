"""Config flow for Google Air Quality."""

import logging
from typing import Any

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import (
    GoogleAirQualityApiError,
    NoDataForLocationError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.selector import LocationSelector

from . import api
from .const import CLOUD_PLATFORM_SCOPE, DOMAIN, OAUTH2_SCOPES

_LOGGER = logging.getLogger(__name__)
CONF_MAP = "map"


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Google Air Quality OAuth2 authentication."""

    DOMAIN = DOMAIN

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"location": LocationSubentryFlowHandler}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Store OAuth token data and prompt user to confirm or change coordinates."""
        token_info = data[CONF_TOKEN]
        scopes = token_info["scope"]

        if CLOUD_PLATFORM_SCOPE not in scopes:
            return self.async_abort(
                reason="missing_scope",
                description_placeholders={"scope": CLOUD_PLATFORM_SCOPE},
            )

        session = aiohttp_client.async_get_clientsession(self.hass)
        auth = api.AsyncConfigFlowAuth(session, data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        client = GoogleAirQualityApi(auth)
        try:
            user_resource_info = await client.get_user_info()
        except GoogleAirQualityApiError as ex:
            _LOGGER.debug("Cannot fetch user info: %s", str(ex))
            return self.async_abort(
                reason="access_not_configured",
            )
        except Exception:
            self.logger.exception("Unknown error occurred")
            return self.async_abort(reason="unknown")
        await self.async_set_unique_id(user_resource_info.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_resource_info.name,
            data=data,
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
            implementation = await async_get_config_entry_implementation(hass, entry)
            web_session = async_get_clientsession(hass)
            oauth_session = OAuth2Session(hass, entry, implementation)
            auth = api.AsyncConfigEntryAuth(web_session, oauth_session)
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
                _LOGGER.error("Could not resolve address for %s,%s:", lat, lon)
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

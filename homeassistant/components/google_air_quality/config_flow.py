"""Config flow for Google Air Quality."""

import asyncio
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
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from . import api
from .const import CLOUD_PLATFORM_SCOPE, DOMAIN, OAUTH2_SCOPES

CONF_MAP = "map"


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Air Quality OAuth2 authentication."""

    DOMAIN = DOMAIN

    _oauth_data: dict[str, Any]

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
        self._oauth_data = data
        token_info = data[CONF_TOKEN]
        scopes = token_info.get("scope", "")

        if CLOUD_PLATFORM_SCOPE not in scopes:
            return self.async_abort(
                reason="missing_scope",
                description_placeholders={"scope": CLOUD_PLATFORM_SCOPE},
            )

        session = aiohttp_client.async_get_clientsession(self.hass)
        auth = api.AsyncConfigFlowAuth(
            session, self._oauth_data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        client = GoogleAirQualityApi(auth)
        try:
            user_resource_info = await client.get_user_info()
        except GoogleAirQualityApiError as ex:
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": str(ex)},
            )
        except Exception:
            self.logger.exception("Unknown error occurred")
            return self.async_abort(reason="unknown")
        await self.async_set_unique_id(user_resource_info.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_resource_info.name,
            data=self._oauth_data,
        )


class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a location."""

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """User flow to add a new location."""
        if user_input is not None:
            entry = self._get_entry()
            hass = self.hass
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    hass, entry
                )
            )
            web_session = async_get_clientsession(hass)
            oauth_session = config_entry_oauth2_flow.OAuth2Session(
                hass, entry, implementation
            )
            auth = api.AsyncConfigEntryAuth(web_session, oauth_session)
            client = GoogleAirQualityApi(auth)
            self._show_form_user()
            location = user_input[CONF_LOCATION]
            lat = location[CONF_LATITUDE]
            lon = location[CONF_LONGITUDE]
            try:
                air_quality_data = await client.async_air_quality(lat, lon)
            except NoDataForLocationError:
                return self._show_form_user(
                    user_input,
                    errors={"base": "no_data_for_location"},
                )
            except GoogleAirQualityApiError as ex:
                return self.async_abort(
                    reason="access_not_configured",
                    description_placeholders={"message": str(ex)},
                )
            except Exception:
                self.logger.exception("Unknown error occurred")
                return self.async_abort(reason="unknown")

            unique_id = f"{lat}_{lon}"
            for existing_subentry in entry.subentries.values():
                if existing_subentry.unique_id == unique_id:
                    return self.async_abort(reason="already_configured")
            data = {
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: lon,
                "region_code": air_quality_data.region_code,
            }
            result = self.async_create_entry(
                title=f"Coordinates {lat}, {lon}",
                data=data,
                unique_id=unique_id,
            )

            async def reload_later() -> None:
                await asyncio.sleep(0)
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
                                "latitude": self.hass.config.latitude,
                                "longitude": self.hass.config.longitude,
                            },
                        ),
                    ): LocationSelector()
                }
            ),
            errors=errors,
        )

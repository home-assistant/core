"""Config flow for Google Air Quality."""

import logging
from typing import Any

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import (
    GoogleAirQualityApiError,
    NoDataForLocationError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_TOKEN,
)
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.selector import LocationSelector

from . import api
from .const import DOMAIN, OAUTH2_SCOPE

CONF_MAP = "map"


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Air Quality OAuth2 authentication."""

    DOMAIN = DOMAIN

    _oauth_data: dict[str, Any]

    schema = vol.Schema({vol.Required(CONF_LOCATION): LocationSelector()})

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": OAUTH2_SCOPE,
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Store OAuth token data and prompt user to confirm or change coordinates."""
        self._oauth_data = data
        token_info = data[CONF_TOKEN]
        scopes = token_info.get("scope", "")
        scope_list = scopes.split()

        if OAUTH2_SCOPE not in scope_list:
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={
                    "message": f"Missing required scope: {OAUTH2_SCOPE}"
                },
            )

        return self._show_form_user()

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle coordinate input and create the config entry."""
        if not user_input:
            return self._show_form_user()

        session = aiohttp_client.async_get_clientsession(self.hass)
        auth = api.AsyncConfigFlowAuth(
            session, self._oauth_data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        client = GoogleAirQualityApi(auth)
        location = user_input[CONF_LOCATION]
        lat = location[CONF_LATITUDE]
        lon = location[CONF_LONGITUDE]

        try:
            user_resource_info = await client.async_air_quality(lat, lon)
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

        await self.async_set_unique_id(unique_id)
        self._oauth_data.update(
            {
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: lon,
                "region_code": user_resource_info.region_code,
            }
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Coordinates {lat}, {lon}", data=self._oauth_data
        )

    def _show_form_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="coordinates",
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

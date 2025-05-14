"""Config flow for Google Photos."""

import logging
from typing import Any

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.exceptions import (
    GooglePhotosApiError,
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
from .const import DOMAIN, OAUTH2_SCOPES

CONF_MAP = "map"


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Photos OAuth2 authentication."""

    DOMAIN = DOMAIN

    _oauth_data: dict[str, Any] | None = None

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

        # async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        # """Create an entry for the flow."""
        # session = aiohttp_client.async_get_clientsession(self.hass)
        # auth = api.AsyncConfigFlowAuth(session, data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        # self.logger.error("Creating Google Photos API client")
        # self.logger.error("data: %s", data)
        # client = GooglePhotosLibraryApi(auth)
        # self.logger.error("data: %s", data)

        # lat = self.hass.config.latitude
        # long = self.hass.config.longitude
        # try:
        #     self.logger.debug("jetzt gehts los")
        #     user_resource_info = await client.get_media_item(lat, long)
        #     self.logger.debug("user_resource_info: %s", user_resource_info)
        # except GooglePhotosApiError as ex:
        #     return self.async_abort(
        #         reason="access_not_configured",
        #         description_placeholders={"message": str(ex)},
        #     )
        # except Exception:
        #     self.logger.exception("Unknown error occurred")
        #     return self.async_abort(reason="unknown")

        # await self.async_set_unique_id(f"{long}_{lat}")

        # self._abort_if_unique_id_configured()
        # return self.async_create_entry(title=f"{long}_{lat}", data=data)

    # async def async_step_coordinates(
    #     self, user_input: dict[str, str] | None = None
    # ) -> ConfigFlowResult:
    #     """Handle the start of the config flow."""
    #     errors: dict[str, str] = {}

    #     if user_input is not None:
    #         # Speichere Standortdaten temporär
    #         self.user_input = user_input
    #         # Wechsle in den OAuth2-Flow
    #         return await self.async_step_auth()

    #     return self.async_show_form(
    #         step_id="user",
    #         data_schema=self.add_suggested_values_to_schema(
    #             vol.Schema(
    #                 {
    #                     vol.Required(
    #                         CONF_LOCATION,
    #                     ): LocationSelector(),
    #                 }
    #             ),
    #             {
    #                 CONF_LOCATION: {
    #                     CONF_LATITUDE: round(self.hass.config.latitude, 6),
    #                     CONF_LONGITUDE: round(self.hass.config.longitude, 6),
    #                 }
    #             },
    #         ),
    #         errors=errors,
    #     )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Store OAuth token data and prompt user to confirm or change coordinates."""
        # Store OAuth token data for the next step
        self._oauth_data = data

        # Show form to ask/confirm coordinates with suggested defaults
        schema = vol.Schema({vol.Required(CONF_LOCATION): LocationSelector()})
        suggested = {
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            }
        }
        return self.async_show_form(
            step_id="coordinates",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors={},
        )

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle coordinate input and create the config entry."""
        if user_input is None:
            return self.async_abort(reason="invalid_location")

        assert self._oauth_data is not None

        # Retrieve OAuth token data
        session = aiohttp_client.async_get_clientsession(self.hass)
        auth = api.AsyncConfigFlowAuth(
            session, self._oauth_data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        self.logger.error("Creating Google Photos API client")
        self.logger.error("data: %s", self._oauth_data)
        client = GoogleAirQualityApi(auth)
        self.logger.error("self._oauth_data: %s", self._oauth_data)
        self.logger.error("user_input: %s", user_input)

        location = user_input[CONF_LOCATION]
        lat = location[CONF_LATITUDE]
        lon = location[CONF_LONGITUDE]

        home = False
        if lat is self.hass.config.latitude and lon is self.hass.config.longitude:
            home = True

        try:
            user_resource_info = await client.async_air_quality(lat, lon)
        except NoDataForLocationError:
            return self.async_abort(
                reason="no_data_for_location",
            )
        except GooglePhotosApiError as ex:
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": str(ex)},
            )
        except Exception:
            self.logger.exception("Unknown error occurred")
            return self.async_abort(reason="unknown")

        if home is True:
            unique_id = "home"
        else:
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

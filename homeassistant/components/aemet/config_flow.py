"""Config flow for AEMET OpenData."""

from collections.abc import Mapping
from typing import Any, override

from aemet_opendata.exceptions import AuthError
from aemet_opendata.interface import AEMET, ConnectionOptions
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandlerWithReload,
)
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import CONF_RADAR_UPDATES, CONF_STATION_UPDATES, DEFAULT_NAME, DOMAIN

API_KEY_URL = "https://opendata.aemet.es/centrodedescargas/altaUsuario"

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_RADAR_UPDATES, default=False): bool,
        probatio.Required(CONF_STATION_UPDATES, default=True): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class AemetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for AEMET OpenData."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude = location[CONF_LATITUDE]
            longitude = location[CONF_LONGITUDE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_api_key(
                user_input[CONF_API_KEY], latitude, longitude
            )
            if not errors:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LATITUDE: latitude,
                        CONF_LONGITUDE: longitude,
                    },
                )

        schema = probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                probatio.Required(CONF_LOCATION): LocationSelector(
                    LocationSelectorConfig(radius=False)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                user_input
                or {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow when the API key is no longer valid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a new API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self._get_reauth_entry()
            errors = await self._async_validate_api_key(
                user_input[CONF_API_KEY],
                entry.data[CONF_LATITUDE],
                entry.data[CONF_LONGITUDE],
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def _async_validate_api_key(
        self, api_key: str, latitude: float, longitude: float
    ) -> dict[str, str]:
        """Validate the API key and return any form errors."""
        options = ConnectionOptions(api_key)
        aemet = AEMET(aiohttp_client.async_get_clientsession(self.hass), options)
        try:
            await aemet.select_coordinates(latitude, longitude)
        except AuthError:
            return {"base": "invalid_api_key"}
        return {}

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandlerWithReload:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandlerWithReload(config_entry, OPTIONS_FLOW)

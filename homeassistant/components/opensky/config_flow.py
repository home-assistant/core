"""Config flow for OpenSky integration."""
from __future__ import annotations

from typing import Any

from aiohttp import BasicAuth
from python_opensky import OpenSky
from python_opensky.exceptions import OpenSkyUnauthenticatedError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RADIUS,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CONTRIBUTING_USER, DEFAULT_NAME, DOMAIN
from .sensor import CONF_ALTITUDE, DEFAULT_ALTITUDE


class OpenSkyConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for OpenSky."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OpenSkyOptionsFlowHandler:
        """Get the options flow for this handler."""
        return OpenSkyOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize user input."""
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                },
                options={
                    CONF_RADIUS: user_input[CONF_RADIUS],
                    CONF_ALTITUDE: user_input[CONF_ALTITUDE],
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_RADIUS): vol.Coerce(float),
                        vol.Required(CONF_LATITUDE): cv.latitude,
                        vol.Required(CONF_LONGITUDE): cv.longitude,
                        vol.Optional(CONF_ALTITUDE): vol.Coerce(float),
                    }
                ),
                {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_ALTITUDE: DEFAULT_ALTITUDE,
                },
            ),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        entry_data = {
            CONF_LATITUDE: import_config.get(CONF_LATITUDE, self.hass.config.latitude),
            CONF_LONGITUDE: import_config.get(
                CONF_LONGITUDE, self.hass.config.longitude
            ),
        }
        self._async_abort_entries_match(entry_data)
        return self.async_create_entry(
            title=import_config.get(CONF_NAME, DEFAULT_NAME),
            data=entry_data,
            options={
                CONF_RADIUS: import_config[CONF_RADIUS] * 1000,
                CONF_ALTITUDE: import_config.get(CONF_ALTITUDE, DEFAULT_ALTITUDE),
            },
        )


class OpenSkyOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """OpenSky Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            authentication = CONF_USERNAME in user_input or CONF_PASSWORD in user_input
            if authentication and CONF_USERNAME not in user_input:
                errors["base"] = "username_missing"
            if authentication and CONF_PASSWORD not in user_input:
                errors["base"] = "password_missing"
            if user_input[CONF_CONTRIBUTING_USER] and not authentication:
                errors["base"] = "no_authentication"
            if authentication and not errors:
                async with OpenSky(
                    session=async_get_clientsession(self.hass)
                ) as opensky:
                    try:
                        await opensky.authenticate(
                            BasicAuth(
                                login=user_input[CONF_USERNAME],
                                password=user_input[CONF_PASSWORD],
                            ),
                            contributing_user=user_input[CONF_CONTRIBUTING_USER],
                        )
                    except OpenSkyUnauthenticatedError:
                        errors["base"] = "invalid_auth"
            if not errors:
                return self.async_create_entry(
                    title=self.options.get(CONF_NAME, "OpenSky"),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_RADIUS): vol.Coerce(float),
                        vol.Optional(CONF_ALTITUDE): vol.Coerce(float),
                        vol.Optional(CONF_USERNAME): str,
                        vol.Optional(CONF_PASSWORD): str,
                        vol.Optional(CONF_CONTRIBUTING_USER, default=False): bool,
                    }
                ),
                user_input or self.options,
            ),
        )

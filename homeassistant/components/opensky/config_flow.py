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
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_RADIUS,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ALTITUDE,
    CONF_CONTRIBUTING_USER,
    DEFAULT_ALTITUDE,
    DEFAULT_NAME,
    DOMAIN,
)


class OpenSkyConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for OpenSky."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OpenSkyOptionsFlowHandler:
        """Get the options flow for this handler."""
        return OpenSkyOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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


class OpenSkyOptionsFlowHandler(OptionsFlow):
    """OpenSky Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                opensky = OpenSky(session=async_get_clientsession(self.hass))
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
                return self.async_create_entry(data=user_input)

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
                user_input or self.config_entry.options,
            ),
        )

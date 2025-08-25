"""Config flow for Shark IQ integration."""

import urllib.parse
import voluptuous as vol
import aiohttp
from sharkiq import Auth0Client

from homeassistant import exceptions
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_REGION
from homeassistant.helpers import selector, aiohttp_client

from .const import (
    DOMAIN,
    LOGGER,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
    SHARKIQ_REGION_ELSEWHERE,
    SHARKIQ_REGION_OPTIONS,
)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid authentication."""




# ------------------------------
# Config Flow
# ------------------------------
SHARKIQ_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(
            CONF_REGION,
            default=SHARKIQ_REGION_DEFAULT,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SHARKIQ_REGION_OPTIONS,
                translation_key="region",
            )
        ),
    }
)


async def _validate_input(hass, data) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    session = aiohttp_client.async_create_clientsession(hass)
    try:
        tokens = await Auth0Client.do_auth0_login(session, data[CONF_USERNAME], data[CONF_PASSWORD])
        LOGGER.debug("Got tokens in config flow: %s", list(tokens.keys()))
    except InvalidAuth:
        raise
    except Exception as err:
        raise CannotConnect from err

    return {"title": data[CONF_USERNAME]}


class SharkIqConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shark IQ."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # fallback
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=SHARKIQ_SCHEMA,
            errors=errors,
        )

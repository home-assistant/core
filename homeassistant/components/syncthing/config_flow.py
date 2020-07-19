"""Config flow for syncthing integration."""
import logging

import requests
import syncthing
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
    HTTP_FORBIDDEN,
)

from .const import CONF_USE_HTTPS, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_USE_HTTPS, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_USE_HTTPS, default=DEFAULT_USE_HTTPS): bool,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    try:
        client = syncthing.Syncthing(
            data[CONF_TOKEN],
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            is_https=data[CONF_USE_HTTPS],
        )
        await hass.async_add_executor_job(client.system.config)
    except syncthing.SyncthingError as err:
        if type(err.__cause__) is requests.exceptions.HTTPError:
            if err.__cause__.response.status_code == HTTP_FORBIDDEN:
                raise InvalidAuth
        raise CannotConnect

    return {"title": f"{DOMAIN}_{data['name']}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for syncthing."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

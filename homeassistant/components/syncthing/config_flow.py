"""Config flow for syncthing integration."""
import logging

import aiosyncthing
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.util.network import normalize_url

from .const import DEFAULT_URL, DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_URL] == normalize_url(data[CONF_URL]):
            raise AlreadyConfigured

    try:
        async with aiosyncthing.Syncthing(
            data[CONF_TOKEN],
            url=data[CONF_URL],
            verify_ssl=data[CONF_VERIFY_SSL],
            loop=hass.loop,
        ) as client:
            await client.system.config()
            return {"title": f"{data[CONF_URL]}"}
    except aiosyncthing.exceptions.UnauthorizedError as error:
        raise InvalidAuth from error
    except Exception as error:
        raise CannotConnect from error


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for syncthing."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_TOKEN] = "invalid_auth"
            except AlreadyConfigured:
                errors[CONF_URL] = "already_configured"
            else:
                user_input[CONF_URL] = normalize_url(user_input[CONF_URL])
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate device is already configured."""

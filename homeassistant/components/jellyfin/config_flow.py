"""Config flow for jellyfin integration."""
from homeassistant.components.jellyfin import (
    CannotConnect,
    InvalidAuth,
    authenticate,
    setup_client,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from jellyfin_apiclient_python import Jellyfin

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {CONF_URL: str, CONF_USERNAME: str, CONF_PASSWORD: str}
)


async def validate_input(hass: core.HomeAssistant, user_input: dict) -> str:
    jellyfin = Jellyfin()
    setup_client(jellyfin)

    url = user_input.get(CONF_URL)
    username = user_input.get(CONF_USERNAME)
    password = user_input.get(CONF_PASSWORD)

    await hass.async_add_executor_job(
        authenticate, jellyfin.get_client(), url, username, password
    )

    return url


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for jellyfin."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                title = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
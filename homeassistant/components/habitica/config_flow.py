"""Config flow for habitica integration."""
from __future__ import annotations

import logging

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_USER, DEFAULT_URL, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_USER): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_URL, default=DEFAULT_URL): str,
    }
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, str]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""

    websession = async_get_clientsession(hass)
    api = HabitipyAsync(
        conf={
            "login": data[CONF_API_USER],
            "password": data[CONF_API_KEY],
            "url": data[CONF_URL] or DEFAULT_URL,
        }
    )
    try:
        await api.user.get(session=websession)
        return {
            "title": f"{data.get('name', 'Default username')}",
            CONF_API_USER: data[CONF_API_USER],
        }
    except ClientResponseError as ex:
        raise InvalidAuth() from ex


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for habitica."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors = {"base": "invalid_credentials"}
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "unknown"}
            else:
                await self.async_set_unique_id(info[CONF_API_USER])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_import(self, import_data):
        """Import habitica config from configuration.yaml."""
        return await self.async_step_user(import_data)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

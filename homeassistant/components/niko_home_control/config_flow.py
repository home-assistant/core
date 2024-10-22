"""Config flow for the Niko home control integration."""
from __future__ import annotations

import ipaddress

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_IP, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .controller import NikoHomeControlController

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_IP): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)

DATA_SCHEMA_ENTITIES = vol.Schema(
    {
        vol.Required("lights", default=True): bool,
        vol.Required("covers", default=True): bool,
        vol.Required("fans", default=True): bool,
    }
)

DATA_SCHEMA_OPTIONAL = vol.Schema(
    {
        vol.Optional("treatAsDevice", default=True): bool,
        vol.Optional("importLocations", default=True): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str | int]:
    """Validate the user input allows us to connect."""
    name = data[CONF_NAME]
    host = data[CONF_HOST]
    port = data[CONF_PORT]

    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise InvalidHost

    if port < 0 or port > 65535:
        raise InvalidPort

    controller = NikoHomeControlController(host, port)

    if not controller:
        raise CannotConnect

    return {"name": name, "host": host, "port": port}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Niko Home Control."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self._config = {}
        self._entities = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                self._config = user_input
                return await self.async_step_entities()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "invalid_host"
            except InvalidPort:
                errors["port"] = "invalid_port"

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_entities(self, user_input=None):
        """Import a config entry."""
        errors = {}
        if user_input is not None:
            self._entities = user_input
            return await self.async_step_optional()

        return self.async_show_form(
            step_id="entities", data_schema=DATA_SCHEMA_ENTITIES, errors=errors
        )

    async def async_step_optional(self, user_input=None):
        """Handle the optional step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=DOMAIN,
                data={
                    "config": self._config,
                    "options": user_input,
                    "entities": self._entities,
                },
            )

        return self.async_show_form(
            step_id="optional", data_schema=DATA_SCHEMA_OPTIONAL, errors=errors
        )

    async def async_step_import(self, import_info):
        """Import a config entry."""
        return await self.async_step_user()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid host."""


class InvalidPort(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid port."""

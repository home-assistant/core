"""Config flow for the Niko home control integration."""
from __future__ import annotations

import ipaddress

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_IP, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .hub import Hub

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_IP): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str | int]:
    """Validate the user input allows us to connect."""
    name = data[CONF_NAME]
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    hub = Hub(hass, name, host, port, None)

    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise InvalidHost

    if port < 0 or port > 65535:
        raise InvalidPort

    if not hub:
        raise CannotConnect

    return {"name": name, "host": host, "port": port}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Niko Home Control."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                return self.async_create_entry(title=DOMAIN, data=user_input)
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid host."""


class InvalidPort(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid port."""

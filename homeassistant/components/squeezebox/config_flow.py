"""Config flow for Logitech Squeezebox integration."""
import logging

from pysqueezebox import Server
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    HTTP_UNAUTHORIZED,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    server = Server(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_PORT],
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
    )

    status = await server.async_query("serverstatus")
    if not status:
        if server.http_status == HTTP_UNAUTHORIZED:
            raise InvalidAuth
        raise CannotConnect

    return status


class SqueezeboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Logitech Squeezebox."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                if "uuid" in info:
                    await self.async_set_unique_id(info["uuid"])
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.get("ip"), data=user_input)
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

    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        try:
            DATA_SCHEMA(user_input)
            info = await validate_input(self.hass, user_input)
            if "uuid" in info:
                await self.async_set_unique_id(info["uuid"])
                self.async_abort(reason="already_configured")
            return self.async_create_entry(title=info.get("ip"), data=user_input)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

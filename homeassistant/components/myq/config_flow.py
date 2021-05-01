"""Config flow for MyQ integration."""
import logging

import pymyq
from pymyq.errors import InvalidCredentialsError, MyQError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        await pymyq.login(data[CONF_USERNAME], data[CONF_PASSWORD], websession)
    except InvalidCredentialsError as err:
        raise InvalidAuth from err
    except MyQError as err:
        raise CannotConnect from err

    return {"title": data[CONF_USERNAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyQ."""

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
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_homekit(self, discovery_info):
        """Handle HomeKit discovery."""
        if self._async_current_entries():
            # We can see myq on the network to tell them to configure
            # it, but since the device will not give up the account it is
            # bound to and there can be multiple myq gateways on a single
            # account, we avoid showing the device as discovered once
            # they already have one configured as they can always
            # add a new one via "+"
            return self.async_abort(reason="already_configured")
        properties = {
            key.lower(): value for (key, value) in discovery_info["properties"].items()
        }
        await self.async_set_unique_id(properties["id"])
        return await self.async_step_user()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

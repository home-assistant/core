"""Config flow for Smart Meter Texas integration."""

import logging
from typing import Any

from aiohttp import ClientError
from smart_meter_texas import Account, Client, ClientSSLContext
from smart_meter_texas.exceptions import (
    SmartMeterTexasAPIError,
    SmartMeterTexasAuthError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    client_ssl_context = ClientSSLContext()
    ssl_context = await client_ssl_context.get_ssl_context()
    client_session = aiohttp_client.async_get_clientsession(hass)
    account = Account(data["username"], data["password"])
    client = Client(client_session, account, ssl_context)

    try:
        await client.authenticate()
    except (TimeoutError, ClientError, SmartMeterTexasAPIError) as error:
        raise CannotConnect from error
    except SmartMeterTexasAuthError as error:
        raise InvalidAuth(error) from error

    # Return info that you want to store in the config entry.
    return {"title": account.username}


class SMTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Meter Texas."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not errors:
                    # Ensure the same account cannot be setup more than once.
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

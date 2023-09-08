"""Config flow for EyeOnWater integration."""
import asyncio
import logging
from typing import Any
from types import MappingProxyType


from aiohttp import ClientError
from pyonwater import Account, Client, EyeOnWaterAPIError, EyeOnWaterAuthError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

CONF_EOW_HOSTNAME_COM = "eyeonwater.com"
CONF_EOW_HOSTNAME_CA = "eyeonwater.ca"

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    },
)


def get_hostname_for_country(hass: core.HomeAssistant) -> str:
    """Return EOW hostname based on HA country."""
    if hass.config.country == "CA":
        return CONF_EOW_HOSTNAME_CA

    # There are some users from Europe that use .com domain
    return CONF_EOW_HOSTNAME_COM


def create_account_from_config(
    hass: core.HomeAssistant,
    data: MappingProxyType[str, Any],
) -> Account:
    """Create account login from config."""
    eow_hostname = get_hostname_for_country(hass)

    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]

    return Account(
        eow_hostname=eow_hostname,
        username=username,
        password=password,
    )


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    client_session = aiohttp_client.async_get_clientsession(hass)
    account = create_account_from_config(hass, data)
    client = Client(client_session, account)

    try:
        await client.authenticate()
    except (asyncio.TimeoutError, ClientError, EyeOnWaterAPIError) as error:
        raise CannotConnect from error
    except EyeOnWaterAuthError as error:
        raise InvalidAuth(error) from error

    # Return info that you want to store in the config entry.
    return {"title": account.username}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EyeOnWater."""

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
            else:
                if not errors:
                    # Ensure the same account cannot be setup more than once.
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

"""Config flow for EyeOnWater integration."""
import asyncio
import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN
from pyonwater import Account, Client, EyeOnWaterAPIError, EyeOnWaterAuthError

CONF_EOW_HOSTNAME_COM = "eyeonwater.com"
CONF_EOW_HOSTNAME_CA = "eyeonwater.ca"

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def create_account_from_config(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> Account:
    """Create account login from config."""
    CountryCode = hass.config.country
    if CountryCode == "US":
        eow_hostname = CONF_EOW_HOSTNAME_COM
    elif CountryCode == "CA":
        eow_hostname = CONF_EOW_HOSTNAME_CA
    else:
        raise CannotConnect(
            f"Unsupported country ({CountryCode}) setup in HomeAssistant."
        )

    metric_measurement_system = hass.config.units is METRIC_SYSTEM
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]

    account = Account(
        eow_hostname=eow_hostname,
        username=username,
        password=password,
        metric_measurement_system=metric_measurement_system,
    )
    return account


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
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

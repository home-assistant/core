"""Config flow for SleepIQ integration."""
import logging

from asyncsleepiq import AsyncSleepIQ, SleepIQTimeoutException, SleepIQLoginException
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    client_session = async_get_clientsession(hass)

    gateway = AsyncSleepIQ(client_session=client_session)
    await gateway.login(data[CONF_EMAIL], data[CONF_PASSWORD])

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_EMAIL]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SleepIQ."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                return self.async_create_entry(title=info["title"], data=user_input)
            except SleepIQTimeoutException:
                errors["base"] = "cannot_connect"
            except SleepIQLoginException as err:
                errors["base"] = "invalid_auth"
                _LOGGER.exception(str(err))
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        await self.async_set_unique_id(user_input[CONF_EMAIL])
        self._abort_if_unique_id_configured()

        return await self.async_step_user(user_input)

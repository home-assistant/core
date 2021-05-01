"""Config flow for Sense integration."""
import logging

from sense_energy import ASyncSenseable, SenseAuthenticationException
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TIMEOUT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACTIVE_UPDATE_RATE, DEFAULT_TIMEOUT, DOMAIN, SENSE_TIMEOUT_EXCEPTIONS

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    timeout = data[CONF_TIMEOUT]
    client_session = async_get_clientsession(hass)

    gateway = ASyncSenseable(
        api_timeout=timeout, wss_timeout=timeout, client_session=client_session
    )
    gateway.rate_limit = ACTIVE_UPDATE_RATE
    await gateway.authenticate(data[CONF_EMAIL], data[CONF_PASSWORD])

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_EMAIL]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sense."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                return self.async_create_entry(title=info["title"], data=user_input)
            except SENSE_TIMEOUT_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            except SenseAuthenticationException:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

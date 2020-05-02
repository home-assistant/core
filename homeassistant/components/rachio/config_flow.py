"""Config flow for Rachio integration."""
import logging

from rachiopy import Rachio
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, HTTP_OK
from homeassistant.core import callback

from .const import (
    CONF_MANUAL_RUN_MINS,
    DEFAULT_MANUAL_RUN_MINS,
    KEY_ID,
    KEY_STATUS,
    KEY_USERNAME,
    RACHIO_API_EXCEPTIONS,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str}, extra=vol.ALLOW_EXTRA)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    rachio = Rachio(data[CONF_API_KEY])
    username = None
    try:
        data = await hass.async_add_executor_job(rachio.person.getInfo)
        _LOGGER.debug("rachio.person.getInfo: %s", data)
        if int(data[0][KEY_STATUS]) != HTTP_OK:
            raise InvalidAuth

        rachio_id = data[1][KEY_ID]
        data = await hass.async_add_executor_job(rachio.person.get, rachio_id)
        _LOGGER.debug("rachio.person.get: %s", data)
        if int(data[0][KEY_STATUS]) != HTTP_OK:
            raise CannotConnect

        username = data[1][KEY_USERNAME]
    # Yes we really do get all these exceptions (hopefully rachiopy switches to requests)
    except RACHIO_API_EXCEPTIONS as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": username}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rachio."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
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

    async def async_step_homekit(self, homekit_info):
        """Handle HomeKit discovery."""
        if self._async_current_entries():
            # We can see rachio on the network to tell them to configure
            # it, but since the device will not give up the account it is
            # bound to and there can be multiple rachio systems on a single
            # account, we avoid showing the device as discovered once
            # they already have one configured as they can always
            # add a new one via "+"
            return self.async_abort(reason="already_configured")
        properties = {
            key.lower(): value for (key, value) in homekit_info["properties"].items()
        }
        await self.async_set_unique_id(properties["id"])
        return await self.async_step_user()

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Rachio."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MANUAL_RUN_MINS,
                    default=self.config_entry.options.get(
                        CONF_MANUAL_RUN_MINS, DEFAULT_MANUAL_RUN_MINS
                    ),
                ): int
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

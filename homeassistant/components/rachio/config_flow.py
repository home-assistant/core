"""Config flow for Rachio integration."""
from http import HTTPStatus
import logging

from rachiopy import Rachio
from requests.exceptions import ConnectTimeout
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_MANUAL_RUN_MINS,
    DEFAULT_MANUAL_RUN_MINS,
    DOMAIN,
    KEY_ID,
    KEY_STATUS,
    KEY_USERNAME,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str}, extra=vol.ALLOW_EXTRA)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    rachio = Rachio(data[CONF_API_KEY])
    username = None
    try:
        data = await hass.async_add_executor_job(rachio.person.info)
        _LOGGER.debug("rachio.person.getInfo: %s", data)
        if int(data[0][KEY_STATUS]) != HTTPStatus.OK:
            raise InvalidAuth

        rachio_id = data[1][KEY_ID]
        data = await hass.async_add_executor_job(rachio.person.get, rachio_id)
        _LOGGER.debug("rachio.person.get: %s", data)
        if int(data[0][KEY_STATUS]) != HTTPStatus.OK:
            raise CannotConnect

        username = data[1][KEY_USERNAME]
    except ConnectTimeout as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise CannotConnect from error

    # Return info that you want to store in the config entry.
    return {"title": username}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rachio."""

    VERSION = 1

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

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle HomeKit discovery."""
        self._async_abort_entries_match()
        await self.async_set_unique_id(
            discovery_info[zeroconf.ATTR_PROPERTIES][zeroconf.ATTR_PROPERTIES_ID]
        )
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Rachio."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
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

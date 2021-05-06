"""Config flow for Tado integration."""
import logging

from PyTado.interface import Tado
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import CONF_FALLBACK, DOMAIN, UNIQUE_ID

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    try:
        tado = await hass.async_add_executor_job(
            Tado, data[CONF_USERNAME], data[CONF_PASSWORD]
        )
        tado_me = await hass.async_add_executor_job(tado.getMe)
    except KeyError as ex:
        raise InvalidAuth from ex
    except RuntimeError as ex:
        raise CannotConnect from ex
    except requests.exceptions.HTTPError as ex:
        if ex.response.status_code > 400 and ex.response.status_code < 500:
            raise InvalidAuth from ex
        raise CannotConnect from ex

    if "homes" not in tado_me or len(tado_me["homes"]) == 0:
        raise NoHomes

    home = tado_me["homes"][0]
    unique_id = str(home["id"])
    name = home["name"]

    return {"title": name, UNIQUE_ID: unique_id}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tado."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                validated = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoHomes:
                errors["base"] = "no_homes"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(validated[UNIQUE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=validated["title"], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_homekit(self, discovery_info):
        """Handle HomeKit discovery."""
        self._async_abort_entries_match({})
        properties = {
            key.lower(): value for (key, value) in discovery_info["properties"].items()
        }
        await self.async_set_unique_id(properties["id"])
        return await self.async_step_user()

    def _username_already_configured(self, user_input):
        """See if we already have a username matching user input configured."""
        existing_username = {
            entry.data[CONF_USERNAME] for entry in self._async_current_entries()
        }
        return user_input[CONF_USERNAME] in existing_username

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for tado."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_FALLBACK, default=self.config_entry.options.get(CONF_FALLBACK)
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoHomes(exceptions.HomeAssistantError):
    """Error to indicate the account has no homes."""

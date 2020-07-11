"""Config flow for Tado integration."""
import logging

from PyTado.interface import Tado
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import CONF_FALLBACK, UNIQUE_ID
from .const import DOMAIN  # pylint:disable=unused-import

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
    except KeyError:
        raise InvalidAuth
    except RuntimeError:
        raise CannotConnect
    except requests.exceptions.HTTPError as ex:
        if ex.response.status_code > 400 and ex.response.status_code < 500:
            raise InvalidAuth
        raise CannotConnect

    if "homes" not in tado_me or len(tado_me["homes"]) == 0:
        raise NoHomes

    home = tado_me["homes"][0]
    unique_id = str(home["id"])
    name = home["name"]

    return {"title": name, UNIQUE_ID: unique_id}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tado."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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

    async def async_step_homekit(self, homekit_info):
        """Handle HomeKit discovery."""
        if self._async_current_entries():
            # We can see tado on the network to tell them to configure
            # it, but since the device will not give up the account it is
            # bound to and there can be multiple tado devices on a single
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
        if self._username_already_configured(user_input):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)

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

"""Config flow for BMW ConnectedDrive integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_SOURCE, CONF_USERNAME
from homeassistant.core import callback

from . import DOMAIN, setup_account
from .const import CONF_ALLOWED_REGIONS, CONF_READ_ONLY, CONF_REGION, CONF_USE_LOCATION

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION): vol.In(CONF_ALLOWED_REGIONS),
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    entry = config_entries.ConfigEntry(
        version=1,
        domain=DOMAIN,
        title=data[CONF_USERNAME],
        data=data,
        source=config_entries.SOURCE_IGNORE,
        connection_class=config_entries.CONN_CLASS_CLOUD_POLL,
        options={
            CONF_READ_ONLY: data.get(CONF_READ_ONLY, False),
            CONF_USE_LOCATION: False,
        },
        system_options={},
    )

    try:
        account = await hass.async_add_executor_job(
            setup_account, entry, hass, entry.data[CONF_USERNAME]
        )
        await hass.async_add_executor_job(account.update)
    except OSError:
        raise InvalidAuth
    except Exception:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": f"{data[CONF_USERNAME]}{data.get(CONF_SOURCE, '')}"}


class BMWConnectedDriveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BMW ConnectedDrive."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            unique_id = f"{user_input[CONF_REGION]}-{user_input[CONF_USERNAME]}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                # pylint: disable=no-member
                if self.context[CONF_SOURCE] == config_entries.SOURCE_IMPORT:
                    info["title"] = f"{info['title']} (configuration.yaml)"

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

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return a BWM ConnectedDrive option flow."""
        return BMWConnectedDriveOptionsFlow(config_entry)


class BMWConnectedDriveOptionsFlow(config_entries.OptionsFlow):
    """Handle a option flow for BMW ConnectedDrive."""

    def __init__(self, config_entry):
        """Initialize BMW ConnectedDrive option flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_account_options()

    async def async_step_account_options(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="account_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_READ_ONLY,
                        default=self.config_entry.options.get(CONF_READ_ONLY, False),
                    ): bool,
                    vol.Optional(
                        CONF_USE_LOCATION,
                        default=self.config_entry.options.get(CONF_USE_LOCATION, False),
                    ): bool,
                }
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

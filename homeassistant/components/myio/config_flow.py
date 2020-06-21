"""Config flow for myIO integration."""
import logging

from myio.comms_thread import CommsThread  # pylint: disable=import-error
from slugify import slugify
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import (  # pylint:disable=unused-import
    CONF_PORT_APP,
    CONF_REFRESH_TIME,
    DEFAULT_REFRESH_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
COMMS_THREAD = CommsThread()

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="myIO-Server"): str,
        vol.Required(CONF_HOST, default="192.168.1.170"): str,
        vol.Required(CONF_PORT, default="80"): int,
        vol.Required(CONF_PORT_APP, default="843"): int,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD, default="admin"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(self, user_input):
        """Initialize."""
        self.message = ""
        self.name = user_input[CONF_USERNAME]
        self.password = user_input[CONF_PASSWORD]
        self.host = user_input[CONF_HOST]
        self.port = user_input[CONF_PORT]
        self.app_port = user_input[CONF_PORT_APP]

    async def authenticate(self, user_input, entries) -> str:
        """Test if we can authenticate with the host."""

        self.message = await COMMS_THREAD.validate(
            self.host, self.port, self.app_port, self.name, self.password
        )
        _LOGGER.debug("message:%s", self.message)

        return self.message

    async def already_check(self, name, entries) -> bool:
        """Test if the server name is already in use."""

        if any(slugify(name) == slugify(entry.data["name"]) for entry in entries):
            return False
        return True


async def validate_input(user_input, entries):
    """Validate the user input allows us to connect.

    Data has the keys from CONFIG_SCHEMA with values provided by the user.
    """
    hub = PlaceholderHub(user_input)

    if not await hub.already_check(user_input[CONF_NAME], entries):
        raise AlreadyConfigured

    message = await hub.authenticate(user_input, entries)
    if message == "cannot_connect":
        raise CannotConnect
    if message == "invalid_auth":
        raise InvalidAuth
    if message == "app_port_problem":
        raise AppPortProblem


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for myIO."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            if not (slugify(user_input[CONF_NAME]).startswith("myio")):
                user_input[CONF_NAME] = f"myIO-{user_input[CONF_NAME]}"
            else:
                temp_list = list(user_input[CONF_NAME])
                temp_list[0] = "m"
                temp_list[1] = "y"
                temp_list[2] = "I"
                temp_list[3] = "O"
                temp_list[4] = "-"
                user_input[CONF_NAME] = "".join(temp_list)

            await self.async_set_unique_id(slugify(user_input[CONF_NAME]))
            self._abort_if_unique_id_configured()

            try:
                await validate_input(user_input, self._async_current_entries())
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except AlreadyConfigured:
                errors["base"] = "already_configured"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except AppPortProblem:
                errors["base"] = "app_port"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        return self._show_form(errors)

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MyIOoptionsFlowHandler(config_entry)


class MyIOoptionsFlowHandler(config_entries.OptionsFlow):
    """Handle myIO options."""

    def __init__(self, config_entry):
        """Initialize myIO options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the myIO options."""
        return await self.async_step_myio_options()

    async def async_step_myio_options(self, user_input=None):
        """Manage the device tracker options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_REFRESH_TIME,
                default=self.config_entry.options.get(
                    CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME
                ),
            ): int,
        }
        return self.async_show_form(
            step_id="myio_options", data_schema=vol.Schema(options)
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """When a configuration name is used yet."""


class AppPortProblem(exceptions.HomeAssistantError):
    """Error to indicate there is not working application port."""

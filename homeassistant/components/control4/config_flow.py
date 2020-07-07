"""Config flow for Control4 integration."""
import logging

import voluptuous as vol

from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import C4Exception, BadCredentials, Unauthorized

from homeassistant import config_entries, core, exceptions
from homeassistant.helpers import config_validation as cv
from homeassistant.core import callback
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
)

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    DEFAULT_LIGHT_TRANSITION_TIME,
    CONF_LIGHT_TRANSITION_TIME,
    CONF_LIGHT_COLD_START_TRANSITION_TIME,
    DEFAULT_LIGHT_COLD_START_TRANSITION_TIME,
)

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


@callback
def configured_instances(hass):
    """Return a set of configured Control4 instances."""
    return {entry.title for entry in hass.config_entries.async_entries(DOMAIN)}


class Control4Validator:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host, username, password):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password
        self.account = C4Account(self.username, self.password)
        self.controller_name = None
        self.director_bearer_token = None
        self.director = None

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the Control4 account API."""
        try:
            """Authenticate with Control4 account"""
            await self.account.getAccountBearerToken()

            """Get controller name"""
            account_controllers = await self.account.getAccountControllers()
            self.controller_name = account_controllers["controllerCommonName"]

            """Get bearer token to communicate with controller locally"""
            self.director_bearer_token = await self.account.getDirectorBearerToken(
                self.controller_name
            )
            return True
        except (BadCredentials, Unauthorized) as exception:
            _LOGGER.error(exception)
            return False

    async def connect_to_director(self) -> bool:
        """Test if we can connect to the local Control4 Director."""
        try:
            self.director = C4Director(self.host, self.director_bearer_token)
            await self.director.getAllItemInfo()
            return True
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error(exception)
            return False


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    hub = Control4Validator(data["host"], data["username"], data["password"])

    if not await hub.authenticate():
        raise InvalidAuth

    if not await hub.connect_to_director():
        raise CannotConnect

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {
        "controller_name": hub.controller_name,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control4."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            try:
                info = await validate_input(self.hass, user_input)
                if info["controller_name"] in configured_instances(self.hass):
                    return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title=info["controller_name"],
                    data={
                        "host": user_input["host"],
                        "username": user_input["username"],
                        "password": user_input["password"],
                    },
                )
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Control4."""

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
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_LIGHT_COLD_START_TRANSITION_TIME,
                    default=self.config_entry.options.get(
                        CONF_LIGHT_COLD_START_TRANSITION_TIME,
                        DEFAULT_LIGHT_COLD_START_TRANSITION_TIME,
                    ),
                ): vol.All(cv.positive_int),
                vol.Optional(
                    CONF_LIGHT_TRANSITION_TIME,
                    default=self.config_entry.options.get(
                        CONF_LIGHT_TRANSITION_TIME, DEFAULT_LIGHT_TRANSITION_TIME
                    ),
                ): vol.All(cv.positive_int),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

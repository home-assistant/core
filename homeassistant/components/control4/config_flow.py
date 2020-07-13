"""Config flow for Control4 integration."""
import logging

from aiohttp import client_exceptions
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import Unauthorized, NotFound
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CONTROLLER_NAME,
    CONF_LIGHT_COLD_START_TRANSITION_TIME,
    CONF_LIGHT_TRANSITION_TIME,
    DEFAULT_LIGHT_COLD_START_TRANSITION_TIME,
    DEFAULT_LIGHT_TRANSITION_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

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
    return {
        entry.data.get(CONF_CONTROLLER_NAME)
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


class Control4Validator:
    """Validates that config details can be used to authenticate and communicate with Control4."""

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
            # Authenticate with Control4 account
            await self.account.getAccountBearerToken()

            # Get controller name
            account_controllers = await self.account.getAccountControllers()
            self.controller_name = account_controllers["controllerCommonName"]

            # Get bearer token to communicate with controller locally
            self.director_bearer_token = (
                await self.account.getDirectorBearerToken(self.controller_name)
            )["token"]
            return True
        except (Unauthorized, NotFound):
            return False

    async def connect_to_director(self) -> bool:
        """Test if we can connect to the local Control4 Director."""
        try:
            self.director = C4Director(self.host, self.director_bearer_token)
            await self.director.getAllItemInfo()
            return True
        except (Unauthorized, client_exceptions.ClientError) as exception:
            _LOGGER.error(exception)
            return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control4."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            hub = Control4Validator(
                user_input["host"], user_input["username"], user_input["password"]
            )
            try:
                if not await hub.authenticate():
                    raise InvalidAuth
                if not await hub.connect_to_director():
                    raise CannotConnect
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if hub.controller_name in configured_instances(self.hass):
                return self.async_abort(reason="already_configured")

            if errors == {}:
                return self.async_create_entry(
                    title=hub.controller_name,
                    data={
                        CONF_HOST: user_input["host"],
                        CONF_USERNAME: user_input["username"],
                        CONF_PASSWORD: user_input["password"],
                        CONF_CONTROLLER_NAME: hub.controller_name,
                    },
                )

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

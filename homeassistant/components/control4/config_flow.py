"""Config flow for Control4 integration."""
from asyncio import TimeoutError as asyncioTimeoutError
import logging

from aiohttp.client_exceptions import ClientError
from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.error_handling import NotFound, Unauthorized
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_CONTROLLER_UNIQUE_ID,
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


class Control4Validator:
    """Validates that config details can be used to authenticate and communicate with Control4."""

    def __init__(self, host, username, password, hass):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password
        self.controller_unique_id = None
        self.director_bearer_token = None
        self.hass = hass

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the Control4 account API."""
        try:
            account_session = aiohttp_client.async_get_clientsession(self.hass)
            account = C4Account(self.username, self.password, account_session)
            # Authenticate with Control4 account
            await account.getAccountBearerToken()

            # Get controller name
            account_controllers = await account.getAccountControllers()
            self.controller_unique_id = account_controllers["controllerCommonName"]

            # Get bearer token to communicate with controller locally
            self.director_bearer_token = (
                await account.getDirectorBearerToken(self.controller_unique_id)
            )["token"]
            return True
        except (Unauthorized, NotFound):
            return False

    async def connect_to_director(self) -> bool:
        """Test if we can connect to the local Control4 Director."""
        try:
            director_session = aiohttp_client.async_get_clientsession(
                self.hass, verify_ssl=False
            )
            director = C4Director(
                self.host, self.director_bearer_token, director_session
            )
            await director.getAllItemInfo()
            return True
        except (Unauthorized, ClientError, asyncioTimeoutError):
            _LOGGER.error("Failed to connect to the Control4 controller")
            return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control4."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            hub = Control4Validator(
                user_input["host"],
                user_input["username"],
                user_input["password"],
                self.hass,
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

            if not errors:
                controller_unique_id = hub.controller_unique_id
                mac = (controller_unique_id.split("_", 3))[2]
                formatted_mac = format_mac(mac)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=controller_unique_id,
                    data={
                        CONF_HOST: user_input["host"],
                        CONF_USERNAME: user_input["username"],
                        CONF_PASSWORD: user_input["password"],
                        CONF_CONTROLLER_UNIQUE_ID: controller_unique_id,
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
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

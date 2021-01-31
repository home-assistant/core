"""Config flow for ConnectedCars.io integration."""
import logging

from connectedcars.client import ConnectedCarsClient
from connectedcars.constants import QUERY_USER, QUERY_VEHICLE_VIN
from connectedcars.exceptions import ConnectedCarsException
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_BASE, CONF_PASSWORD, CONF_USERNAME

from .const import (  # pylint:disable=unused-import
    CONF_NAMESPACE,
    CONF_TITLE,
    DEFAULT_NAMESPACE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAMESPACE, default=DEFAULT_NAMESPACE): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConnectedcarsApiHandler:
    """Connected Cars.io API connector class."""

    def __init__(self, namespace):
        """Initialize."""
        self.namespace = namespace
        self.vin = None
        self.client = None
        self.user_data = None

    async def authenticate(self, username, password) -> bool:
        """Test if we can authenticate with the namespace."""
        self.client = ConnectedCarsClient(username, password, self.namespace)

        try:
            self.user_data = await self.client.async_query(QUERY_USER)
        except ConnectedCarsException:
            return False

        return True

    async def get_email(self) -> str:
        """Will get the email address of the account holder."""
        if not self.user_data:
            self.user_data = await self.client.async_query(QUERY_USER)

        return self.user_data["data"]["viewer"]["email"]

    async def get_vin(self) -> str:
        """Will get the vin identifier of the car."""
        if not self.vin:
            response = await self.client.async_query(QUERY_VEHICLE_VIN)
            # This integration only collects data of the first vehicle (array position 0)
            self.vin = response["data"]["viewer"]["vehicles"][0]["vehicle"]["vin"]

        return self.vin


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ConnectedCars.io."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                ccah = ConnectedcarsApiHandler(user_input[CONF_NAMESPACE])

                if not await ccah.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                ):
                    raise InvalidAuth

                try:
                    email = await ccah.get_email()
                except ConnectedCarsException as exception:
                    raise CannotGetEmail from exception

                try:
                    vin = await ccah.get_vin()
                except ConnectedCarsException as exception:
                    raise CannotGetVin from exception

                info = {CONF_TITLE: f"{email} - {vin}"}

                # Check if already configured
                await self.async_set_unique_id(info[CONF_TITLE])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info[CONF_TITLE], data=user_input)
            except CannotGetEmail:
                errors[CONF_BASE] = "cannot_get_email"
                _LOGGER.error("Unable to find your email from connectedcars.io")
            except CannotGetVin:
                errors[CONF_BASE] = "cannot_get_vin"
                _LOGGER.error("Unable to find a car vin-name from connectedcars.io")
            except InvalidAuth:
                errors[CONF_BASE] = "invalid_auth"
                _LOGGER.error("Unable to login to ConnectedCars.io, wrong user/pass")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors[CONF_BASE] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotGetEmail(exceptions.HomeAssistantError):
    """Error to indicate we cannot find email of user."""


class CannotGetVin(exceptions.HomeAssistantError):
    """Error to indicate we cannot find vin of car."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

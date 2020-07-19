"""Config flow for ConnectedCars.io integration."""
import logging

from connectedcars import ConnectedCarsClient, ConnectedCarsException
import nest_asyncio
import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import COMPLETE_QUERY_USER, COMPLETE_QUERY_VIN, DEFAULT_NAMESPACE, DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("namespace", default=DEFAULT_NAMESPACE): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("vin"): str,
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
        client = ConnectedCarsClient(username, password, self.namespace)

        self.client = client

        self.user_data = await client.async_query(COMPLETE_QUERY_USER)

        return True

    async def get_email(self) -> str:
        """Will get the email adress of the account holder."""

        if not self.user_data:
            self.user_data = await self.client.async_query(COMPLETE_QUERY_USER)

        email = self.user_data["data"]["viewer"]["email"]

        return email

    async def get_vin(self, userinput_vin) -> str:
        """Will get the vin identifier of the car."""

        if not self.vin:
            response = await self.client.async_query(COMPLETE_QUERY_VIN)
            # This needs to lookup the "userinput_vin" to see if it can be found in the result, not just take the first car
            vin = response["data"]["viewer"]["vehicles"][0]["vehicle"]["vin"]
            self.vin = vin

        return self.vin


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    nest_asyncio.apply()

    ccah = ConnectedcarsApiHandler(data["namespace"])

    if not await ccah.authenticate(data["username"], data["password"]):
        raise InvalidAuth

    try:
        email = await ccah.get_email()
        userinput_vin = None
        # if not data["vin"]: ## Do this somehow
        #     userinput_vin = data["vin"]
        vin = await ccah.get_vin(userinput_vin)
    except ConnectedCarsException as exception:
        raise CannotGetVin from exception

    integration_title = f"{email} - {vin}"

    # Return info that you want to store in the config entry.
    return {"title": integration_title}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ConnectedCars.io."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                # Check if already configured
                await self.async_set_unique_id(info["title"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotGetVin:
                errors["base"] = "cannot_get_vin"
                _LOGGER.error("Unable to find a car vin-name from connectedcars.io")
            except InvalidAuth:
                errors["base"] = "invalid_auth"
                _LOGGER.error("Unable to login to ConnectedCars.io, wrong user/pass")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotGetVin(exceptions.HomeAssistantError):
    """Error to indicate we cannot find vin of car."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

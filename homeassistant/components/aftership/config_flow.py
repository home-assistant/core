"""Config flow for aftership integration."""
import logging

from pyaftership.tracker import Tracking
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_NAME, HTTP_OK
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default="My AfterShip Packages"): str,
        vol.Required(CONF_API_KEY, default=""): str,
    }
)


class AfterShipTest:
    """Placeholder class to make tests pass."""

    def __init__(self, hass, session, api_key):
        """Initialize."""
        self.api_key = api_key
        self.hass = hass
        self.session = session

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        aftership = Tracking(self.hass.loop, self.session, self.api_key)

        await aftership.get_trackings()

        if not aftership.meta or aftership.meta["code"] != HTTP_OK:
            _LOGGER.error(
                "No tracking data found. Check API key is correct: %s", aftership.meta
            )
            return False

        return True


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    hub = AfterShipTest(hass, session, data[CONF_API_KEY])

    if not await hub.authenticate():
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "AfterShip", "api_key": data[CONF_API_KEY]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AfterShip."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                unique_id = "aftership_" + user_input["api_key"].split("-")[0]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                user_input["unique_id"] = unique_id
                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                print(Exception)
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

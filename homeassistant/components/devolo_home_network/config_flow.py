"""Config flow for devolo Home Network integration."""
import logging

from devolo_plc_api.device import Device
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

# TODO PASSWORD needs to be optional
STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_IP_ADDRESS): str, vol.Optional(CONF_PASSWORD): str}
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host):
        """Initialize."""
        self.host = host

    async def authenticate(self, username, password) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    device = Device(data[CONF_IP_ADDRESS])

    if data.get(CONF_PASSWORD):
        device.password = data.get(CONF_PASSWORD)

    await device.async_connect()

    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    # hub = PlaceholderHub(data["host"])

    # if not await hub.authenticate(data["username"], data["password"]):
    #     raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "Name of the device"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for devolo Home Network."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.device = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)

            # TODO: Move this to another place --> validate input
            # Can't be moved atm because we have not function for validating the input.
            device = Device(user_input[CONF_IP_ADDRESS])

            if user_input.get(CONF_PASSWORD):
                device.password = user_input.get(CONF_PASSWORD)

            await device.async_connect()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(device.serial_number)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zerooconf discovery."""
        if discovery_info is None:
            return self.async_abort(reason="cannot_connect")

        if discovery_info["properties"]["MT"] in ["2600", "2601"]:
            return self.async_abort(reason="devolo Home Control Gateway")

        await self.async_set_unique_id(discovery_info["properties"]["SN"])
        self._abort_if_unique_id_configured()

        # self.device = Device(ip=discovery_info['host'], deviceapi=discovery_info['properties'])
        self.device = Device(ip=discovery_info["host"])

        self.context["title_placeholders"] = {
            "name": discovery_info["hostname"].split(".")[0],
            "serial_number": discovery_info["properties"]["SN"],
        }
        print(self.context)
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Handle a flow initiated by zeroconf."""
        if user_input is not None:
            self.device.password = user_input[CONF_PASSWORD]
            await self.device.async_connect()
            title = f"{self.device.ip}"
            return self.async_create_entry(
                title=title, data={CONF_IP_ADDRESS: self.device.ip}
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD, default=""): str}),
            description_placeholders={"host_name": self.device.ip},
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

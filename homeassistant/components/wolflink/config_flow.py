"""Config flow for Wolf SmartSet Service integration."""
import logging

from httpcore._exceptions import ConnectError
import voluptuous as vol
from wolf_smartset.token_auth import InvalidAuth
from wolf_smartset.wolf_client import WolfClient

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wolf SmartSet Service."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize with empty username and password."""
        self.username = None
        self.password = None
        self.fetched_systems = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step to get connection parameters."""
        errors = {}
        if user_input is not None:
            wolf_client = WolfClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            try:
                self.fetched_systems = await wolf_client.fetch_system_list()
            except ConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.username = user_input[CONF_USERNAME]
                self.password = user_input[CONF_PASSWORD]
                return await self.async_step_device()
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_device(self, user_input=None):
        """Allow user to select device from devices connected to specified account."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["device_name"],
                data={
                    "username": self.username,
                    "password": self.password,
                    "device_name": user_input["device_name"],
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required("device_name"): vol.In(
                    [info.name for info in self.fetched_systems]
                )
            }
        )
        return self.async_show_form(
            step_id="device", data_schema=data_schema, errors=errors
        )

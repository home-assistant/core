"""Config flow for user setup."""

import logging
from typing import Any, Dict

from requests import ConnectTimeout, HTTPError
from salus.api import Api
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

# pylint: disable=unused-import
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def validate_input(hass: HomeAssistantType, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # constructor does login call
    Api(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )

    return True


def get_salus_devices(hass: HomeAssistantType, data: dict) -> Dict[str, Any]:
    """Get a list of available Salus devices in user account."""
    api = Api(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )
    return api.get_devices()


class SalusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Salus integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize SalusConfigFlow data updater."""
        self.user_data = None
        self.devices = []

        super().__init__()

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        errors = {}
        default_username = ""

        if user_input is not None:
            default_username = user_input[CONF_USERNAME]
            try:
                await self.hass.async_add_executor_job(
                    validate_input, self.hass, user_input
                )
            except (ConnectTimeout, HTTPError):
                errors["base"] = "cannot_connect"
            except Exception as error:  # pylint: disable=broad-except
                if error.__str__() == "Invalid credentials":
                    errors["base"] = "invalid_auth"
                else:
                    _LOGGER.exception("Unexpected exception")
                    return self.async_abort(reason="unknown")
            else:
                self.user_data = user_input
                self.devices = await self.hass.async_add_executor_job(
                    get_salus_devices, self.hass, user_input
                )

                return await self.async_step_device()

        form_schema = {
            vol.Required(CONF_USERNAME, default=default_username): str,
            vol.Required(CONF_PASSWORD): str,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(form_schema),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        """Second step to choose device to configure in this process."""
        errors = {}

        if user_input is not None:
            data = {}
            device_name = user_input[CONF_DEVICE]
            device_id = next(d.device_id for d in self.devices if d.name == device_name)

            await self.async_set_unique_id(f"salus-{device_id}")
            self._abort_if_unique_id_configured()

            data[CONF_USERNAME] = self.user_data[CONF_USERNAME]
            data[CONF_PASSWORD] = self.user_data[CONF_PASSWORD]
            data[CONF_DEVICE] = device_id

            return self.async_create_entry(title=device_name, data=data)

        device_names = [d.name for d in self.devices]

        form_schema = {
            vol.Required(CONF_DEVICE): vol.In(device_names),
        }

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(form_schema),
            errors=errors,
        )

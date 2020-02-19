"""Config flow for Roku."""
import socket
from urllib.parse import urlparse

from roku import Roku, RokuException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
)
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME

from .const import CONF_SERIAL_NUMBER, DOMAIN

DATA_SCHEMA_USER = vol.Schema({vol.Required(CONF_HOST): str,})

RESULT_NOT_FOUND = "not_found"
RESULT_ROKU_ERROR = "roku_error"
RESULT_SUCCESS = "success"


class RokuConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Roku config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._ip = None
        self._name = None

    def _get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                CONF_IP_ADDRESS: self._ip,
                CONF_NAME: self._name,
            },
        )

    def _try_connect(self):
        """Try to connect """
        roku = Roku(self._host)

        try:
            _device_info = roku.device_info
            return RESULT_SUCCESS
        except OSError:
            return RESULT_NOT_FOUND
        except RokuException:
            return RESULT_ROKU_ERROR

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            ip_address = await self.hass.async_add_executor_job(
                socket.gethostbyname, user_input[CONF_HOST]
            )

            await self.async_set_unique_id(ip_address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            self._name = self._host = user_input[CONF_HOST]
            self._ip = ip_address

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self._get_entry()
            elif result != RESULT_ROKU_ERROR:
                return self.async_abort(reason=result)

            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )

    async def async_step_ssdp(self, discovery_info=None):
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        ip_address = await self.hass.async_add_executor_job(socket.gethostbyname, host)

        await self.async_set_unique_id(ip_address)
        self._abort_if_unique_id_configured()

        self._host = host
        self._ip = ip_address
        self._name = discovery_info[ATTR_UPNP_FRIENDLY_NAME]

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            result = await self.hass.async_add_executor_job(self._try_connect)

            if result != RESULT_SUCCESS:
                return self.async_abort(reason=result)
            return self._get_entry()

        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": self._name},
        )

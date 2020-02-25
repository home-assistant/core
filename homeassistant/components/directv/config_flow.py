"""Config flow for DirecTV."""
import logging
import socket
from urllib.parse import urlparse

from DirectPy import DIRECTV
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.ssdp import ATTR_SSDP_LOCATION
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_NAME, DEFAULT_PORT
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def get_ip(hass: HomeAssistant, host):
    """Translate hostname to IP address."""
    if host is None:
        return None

    return await hass.async_add_executor_job(socket.gethostbyname, host)


async def get_device_version(hass: HomeAssistant, host, port=DEFAULT_PORT, device="0"):
    """Test the device connection by retreiving the version info."""
    dtv = DIRECTV(host, port, device)

    try:
        _device_info = dtv.get_version()
        if not _device_info:
            raise CannotConnect
    except (OSError, RequestException) as exception:
        raise CannotConnect from exception


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    await hass.async_add_executor_job(
        get_device_version, data["host"], data["port"], data["device"]
    )

    # Return info that you want to store in the config entry.
    return {
        "title": data["title"],
        "host": data["host"],
        "port": data["port"],
        "device": data["device"],
    }


class DirecTVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DirecTV."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._ip = None
        self._name = None

    async def async_step_import(self, user_input=None):
        """Handle a flow initialized by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by user."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = ERROR_UNKNOWN

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, discovery_info=None):
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        ip_address = await get_ip(self.hass, host)

        await self.async_set_unique_id(ip_address)
        self._abort_if_unique_id_configured()

        self._host = host
        self._ip = self.context[CONF_IP_ADDRESS] = ip_address
        self._name = DEFAULT_NAME

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(self, user_input=None):
        """Handle user-confirmation of discovered device."""
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                return self.async_abort(reason=ERROR_CANNOT_CONNECT)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason=ERROR_UNKNOWN)

        return self.async_show_form(
            step_id="ssdp_confirm", description_placeholders={"title": self._name},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

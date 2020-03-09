"""Config flow for DirecTV."""
import logging
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from DirectPy import DIRECTV
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_SERIAL
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import HomeAssistantType

from .const import DEFAULT_PORT
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


def get_ip(host: str) -> str:
    """Translate hostname to IP address."""
    if host is None:
        return None

    return socket.gethostbyname(host)


def get_dtv_version(host: str, port: int = DEFAULT_PORT) -> Any:
    """Test the device connection by retrieving the receiver version info."""
    try:
        # directpy does IO in constructor.
        dtv = DIRECTV(host, port)
        return dtv.get_version()
    except (OSError, RequestException) as exception:
        raise CannotConnect from exception


async def validate_input(hass: HomeAssistantType, data: Dict) -> Dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    host = await hass.async_add_executor_job(get_ip, data["host"])
    version_info = await hass.async_add_executor_job(get_dtv_version, host)

    return {
        "title": host,
        "host": host,
        "receiver_id": "".join(version_info["receiverId"].split()),
    }


class DirecTVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DirecTV."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def _show_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors or {},
        )

    async def async_step_import(
        self, user_input: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by user."""
        errors = {}

        if not user_input:
            return await self._show_form()

        try:
            info = await validate_input(self.hass, user_input)
            user_input[CONF_HOST] = info[CONF_HOST]
        except CannotConnect:
            errors["base"] = ERROR_CANNOT_CONNECT
            return await self._show_form(errors)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = ERROR_UNKNOWN
            return await self._show_form(errors)

        await self.async_set_unique_id(info["receiver_id"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=info["title"], data=user_input)

    async def async_step_ssdp(
        self, discovery_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        host = await self.hass.async_add_executor_job(get_ip, host)
        receiver_id = discovery_info[ATTR_UPNP_SERIAL][4:]  # strips off RID-

        await self.async_set_unique_id(receiver_id)
        self._abort_if_unique_id_configured()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {CONF_HOST: host, CONF_NAME: host, "title_placeholders": {"name": host}}
        )

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(
        self, user_input: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle user-confirmation of discovered device."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        name = self.context.get(CONF_NAME)

        if user_input is not None:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            user_input[CONF_HOST] = self.context.get(CONF_HOST)

            try:
                await validate_input(self.hass, user_input)
                return self.async_create_entry(title=name, data=user_input)
            except CannotConnect:
                return self.async_abort(reason=ERROR_CANNOT_CONNECT)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason=ERROR_UNKNOWN)

        return self.async_show_form(
            step_id="ssdp_confirm", description_placeholders={"name": name},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

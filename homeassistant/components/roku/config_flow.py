"""Config flow for Roku."""
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from roku import Roku, RokuException
import voluptuous as vol

from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
)
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN  # pylint: disable=unused-import

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"


def get_ip(host: str) -> str:
    """Translate hostname to IP address."""
    if host is None:
        return None
    return socket.gethostbyname(host)


def get_roku_device_info(host: str) -> Any:
    """Connect to Roku device."""
    roku = Roku(host)

    try:
        device_info = roku.device_info
        return device_info
    except (OSError, RokuException) as exception:
        raise CannotConnect from exception


async def validate_input(hass: HomeAssistantType, data: Dict) -> Dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    host = await hass.async_add_executor_job(get_ip, data["host"])
    device_info = await hass.async_add_executor_job(get_roku_device_info, host)

    return {
        "title": host,
        "host": host,
        "serial_num": device_info.serial_num,
    }


class RokuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Roku config flow."""

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
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""
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
            errors["base"] = ERROR_UNKNOWN
            return await self._show_form(errors)

        await self.async_set_unique_id(info["serial_num"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=info["title"], data=user_input)

    async def async_step_ssdp(
        self, discovery_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        host = await self.hass.async_add_executor_job(get_ip, host)
        name = discovery_info[ATTR_UPNP_FRIENDLY_NAME]
        serial_num = discovery_info[ATTR_UPNP_SERIAL]

        await self.async_set_unique_id(serial_num)
        self._abort_if_unique_id_configured()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {CONF_HOST: host, CONF_NAME: name, "title_placeholders": {"name": host}}
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
            user_input[CONF_NAME] = name

            try:
                await validate_input(self.hass, user_input)
                return self.async_create_entry(title=name, data=user_input)
            except CannotConnect:
                return self.async_abort(reason=ERROR_CANNOT_CONNECT)
            except Exception:  # pylint: disable=broad-except
                return self.async_abort(reason=ERROR_UNKNOWN)

        return self.async_show_form(
            step_id="ssdp_confirm", description_placeholders={"name": name},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

"""Config flow for Roku."""
import logging
from socket import gaierror as SocketGIAError
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from requests.exceptions import RequestException
from roku import Roku, RokuException
import voluptuous as vol

from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
)
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN  # pylint: disable=unused-import

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

_LOGGER = logging.getLogger(__name__)


def validate_input(data: Dict) -> Dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    roku = Roku(data["host"])
    device_info = roku.device_info

    return {
        "title": data["host"],
        "host": data["host"],
        "serial_num": device_info.serial_num,
    }


class RokuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Roku config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    @callback
    def _show_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
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
        if not user_input:
            return self._show_form()

        errors = {}

        try:
            info = await self.hass.async_add_executor_job(validate_input, user_input)
        except (SocketGIAError, RequestException, RokuException):
            errors["base"] = ERROR_CANNOT_CONNECT
            return self._show_form(errors)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error trying to connect.")
            return self.async_abort(reason=ERROR_UNKNOWN)

        await self.async_set_unique_id(info["serial_num"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=info["title"], data=user_input)

    async def async_step_ssdp(
        self, discovery_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        name = discovery_info[ATTR_UPNP_FRIENDLY_NAME]
        serial_num = discovery_info[ATTR_UPNP_SERIAL]

        await self.async_set_unique_id(serial_num)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

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
                await self.hass.async_add_executor_job(validate_input, user_input)
                return self.async_create_entry(title=name, data=user_input)
            except (SocketGIAError, RequestException, RokuException):
                return self.async_abort(reason=ERROR_CANNOT_CONNECT)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown error trying to connect.")
                return self.async_abort(reason=ERROR_UNKNOWN)

        return self.async_show_form(
            step_id="ssdp_confirm", description_placeholders={"name": name},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

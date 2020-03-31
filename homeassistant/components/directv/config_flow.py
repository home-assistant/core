"""Config flow for DirecTV."""
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from DirectPy import DIRECTV
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_SERIAL
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DEFAULT_PORT
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


def validate_input(data: Dict) -> Dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    dtv = DIRECTV(data["host"], DEFAULT_PORT, determine_state=False)
    version_info = dtv.get_version()

    return {
        "title": data["host"],
        "host": data["host"],
        "receiver_id": "".join(version_info["receiverId"].split()),
    }


class DirecTVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DirecTV."""

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
        """Handle a flow initialized by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by user."""
        if not user_input:
            return self._show_form()

        errors = {}

        try:
            info = await self.hass.async_add_executor_job(validate_input, user_input)
            user_input[CONF_HOST] = info[CONF_HOST]
        except RequestException:
            errors["base"] = ERROR_CANNOT_CONNECT
            return self._show_form(errors)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason=ERROR_UNKNOWN)

        await self.async_set_unique_id(info["receiver_id"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=info["title"], data=user_input)

    async def async_step_ssdp(
        self, discovery_info: Optional[DiscoveryInfoType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        receiver_id = discovery_info[ATTR_UPNP_SERIAL][4:]  # strips off RID-

        await self.async_set_unique_id(receiver_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

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
                await self.hass.async_add_executor_job(validate_input, user_input)
                return self.async_create_entry(title=name, data=user_input)
            except (OSError, RequestException):
                return self.async_abort(reason=ERROR_CANNOT_CONNECT)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason=ERROR_UNKNOWN)

        return self.async_show_form(
            step_id="ssdp_confirm", description_placeholders={"name": name},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

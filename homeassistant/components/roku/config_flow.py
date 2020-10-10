"""Config flow for Roku."""
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from rokuecp import Roku, RokuError
import voluptuous as vol

from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
)
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN  # pylint: disable=unused-import

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistantType, data: Dict) -> Dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    roku = Roku(data[CONF_HOST], session=session)
    device = await roku.update()

    return {
        "title": device.info.name,
        "serial_number": device.info.serial_number,
    }


class RokuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Roku config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Set up the instance."""
        self.discovery_info = {}

    @callback
    def _show_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors or {},
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
            info = await validate_input(self.hass, user_input)
        except RokuError:
            _LOGGER.debug("Roku Error", exc_info=True)
            errors["base"] = ERROR_CANNOT_CONNECT
            return self._show_form(errors)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error trying to connect")
            return self.async_abort(reason=ERROR_UNKNOWN)

        await self.async_set_unique_id(info["serial_number"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        return self.async_create_entry(title=info["title"], data=user_input)

    async def async_step_ssdp(
        self, discovery_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        name = discovery_info[ATTR_UPNP_FRIENDLY_NAME]
        serial_number = discovery_info[ATTR_UPNP_SERIAL]

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update({"title_placeholders": {"name": name}})

        self.discovery_info.update({CONF_HOST: host, CONF_NAME: name})

        try:
            await validate_input(self.hass, self.discovery_info)
        except RokuError:
            _LOGGER.debug("Roku Error", exc_info=True)
            return self.async_abort(reason=ERROR_CANNOT_CONNECT)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error trying to connect")
            return self.async_abort(reason=ERROR_UNKNOWN)

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(
        self, user_input: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handle user-confirmation of discovered device."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        if user_input is None:
            return self.async_show_form(
                step_id="ssdp_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )

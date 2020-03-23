"""Config flow for DirecTV."""
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from directv import DIRECTV, DIRECTVError
import voluptuous as vol

from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_SERIAL
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, SOURCE_SSDP, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_RECEIVER_ID
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"


class DirecTVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DirecTV."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_import(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by configuration file."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def async_step_ssdp(
        self, discovery_info: Optional[DiscoveryInfoType] = None
    ) -> Dict[str, Any]:
        """Handle SSDP discovery."""
        if discovery_info is None:
            return self.async_abort(reason=ERROR_CANNOT_CONNECT)

        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        receiver_id = None

        if discovery_info.get(ATTR_UPNP_SERIAL):
            receiver_id = discovery_info[ATTR_UPNP_SERIAL][4:]  # strips off RID-

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {
                CONF_HOST: host,
                CONF_NAME: host,
                CONF_RECEIVER_ID: receiver_id,
                "title_placeholders": {"name": host},
            }
        )

        # Prepare configuration flow
        return await self._handle_config_flow(discovery_info, True)

    async def async_step_ssdp_confirm(
        self, user_input: ConfigType = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by SSDP."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(
        self, user_input: Optional[ConfigType] = None, prepare: bool = False
    ) -> Dict[str, Any]:
        """Config flow handler for DirecTV."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        source = self.context.get("source")

        # Request user input, unless we are preparing discovery flow
        if user_input is None and not prepare:
            if source == SOURCE_SSDP:
                return self._show_confirm_dialog()
            return self._show_setup_form()

        if source == SOURCE_SSDP:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            user_input[CONF_HOST] = self.context.get(CONF_HOST)
            user_input[CONF_RECEIVER_ID] = self.context.get(CONF_RECEIVER_ID)

        if user_input.get(CONF_RECEIVER_ID) is None or not prepare:
            session = async_get_clientsession(self.hass)
            directv = DIRECTV(user_input[CONF_HOST], session=session)
            try:
                device = await directv.update()
            except DIRECTVError:
                if source == SOURCE_SSDP:
                    return self.async_abort(reason=ERROR_CANNOT_CONNECT)
                return self._show_setup_form({"base": ERROR_CANNOT_CONNECT})
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason=ERROR_UNKNOWN)
            user_input[CONF_RECEIVER_ID] = device.info.receiver_id

        # Check if already configured
        await self.async_set_unique_id(user_input[CONF_RECEIVER_ID])
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        title = user_input[CONF_HOST]
        if source == SOURCE_SSDP:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            title = self.context.get(CONF_NAME)

        if prepare:
            return await self.async_step_ssdp_confirm()

        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_RECEIVER_ID: user_input[CONF_RECEIVER_ID],
            },
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    def _show_confirm_dialog(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the confirm dialog to the user."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        name = self.context.get(CONF_NAME)
        return self.async_show_form(
            step_id="ssdp_confirm",
            description_placeholders={"name": name},
            errors=errors or {},
        )

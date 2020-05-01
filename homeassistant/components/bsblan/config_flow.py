"""Config flow for BSB-Lan integration."""
import logging
from typing import Any, Dict, Optional

from bsblan import BSBLan, BSBLanError, Info
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import ConfigType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (  # pylint:disable=unused-import
    CONF_DEVICE_IDENT,
    CONF_PASSKEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BSBLanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BSBLan config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        try:
            info = await self._get_bsblan_info(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                passkey=user_input[CONF_PASSKEY],
            )
        except BSBLanError:
            return self._show_setup_form({"base": "connection_error"})

        # Check if already configured
        await self.async_set_unique_id(info.device_identification)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=info.device_identification,
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_PASSKEY: user_input[CONF_PASSKEY],
                CONF_DEVICE_IDENT: info.device_identification,
            },
        )

    async def async_step_zeroconf(
        # self, user_input: Optional[ConfigType] = None
        self,
        discovery_info: DiscoveryInfoType,
    ) -> Dict[str, Any]:
        """Handle zeroconf discovery."""
        if discovery_info.get(CONF_PORT) is None:
            return self.async_abort(reason="connection_error")

        # Hostname is format: my-ke.local.
        host = discovery_info["hostname"].rstrip(".")
        try:
            info = await self._get_bsblan_info(host, discovery_info[CONF_PORT])
        except BSBLanError:
            return self.async_abort(reason="connection_error")

        # Check if already configured
        await self.async_set_unique_id(info.device_identification)
        self._abort_if_unique_id_configured()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {
                CONF_HOST: host,
                CONF_PORT: discovery_info[CONF_PORT],
                CONF_PASSKEY: discovery_info[CONF_PASSKEY],
                CONF_DEVICE_IDENT: info.device_identification,
                "title_placeholders": {"device_ident": info.device_identification},
            }
        )

        # Prepare configuration flow
        return self._show_confirm_dialog()

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
    async def async_step_zeroconf_confirm(
        self, user_input: ConfigType = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by zeroconf."""
        try:
            info = await self._get_bsblan_info(
                self.context.get(CONF_HOST),
                self.context.get(CONF_PORT),
                self.context.get(CONF_PASSKEY),
            )
        except BSBLanError:
            return self.async_abort(reason="connection_error")

        # Check if already configured
        await self.async_set_unique_id(info.device_identification)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.context.get(CONF_DEVICE_IDENT),
            data={
                CONF_HOST: self.context.get(CONF_HOST),
                CONF_PORT: self.context.get(CONF_PORT),
                CONF_PASSKEY: self.context.get(CONF_PASSKEY),
                CONF_DEVICE_IDENT: self.context.get(CONF_DEVICE_IDENT),
            },
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=80): int,
                    vol.Optional(CONF_PASSKEY, default=""): str,
                }
            ),
            errors=errors or {},
        )

    def _show_confirm_dialog(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the confirm dialog to the user."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        name = self.context.get(CONF_NAME)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": name},
            errors=errors or {},
        )

    async def _get_bsblan_info(
        self, host: str, passkey: Optional[str], port: int
    ) -> Info:
        """Get device information from an BSBLan device."""
        session = async_get_clientsession(self.hass)
        _LOGGER.debug("request bsblan.info:")
        bsblan = BSBLan(
            host, passkey=passkey, port=port, session=session, loop=self.hass.loop
        )
        test = await bsblan.info()
        _LOGGER.debug("get bsblan.info: %s", test)
        return await bsblan.info()

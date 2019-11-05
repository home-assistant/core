"""Config flow to configure the AdGuard Home integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from wled import WLED, WLEDConnectionError

from homeassistant import config_entries
from homeassistant.components.wled.const import DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.helpers import ConfigType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class WLEDFlowHandler(ConfigFlow):
    """Handle a WLED config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize WLED flow."""
        pass

    async def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    async def _show_confirm_dialog(
        self, errors: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Show the setup form to the user."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        name = self.context.get(CONF_NAME)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": name},
            errors=errors or {},
        )

    async def _handle_config_flow(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        source = self.context.get("source")

        if user_input is None:
            if source == SOURCE_ZEROCONF:
                return await self._show_confirm_dialog()
            return await self._show_setup_form()

        if source == SOURCE_ZEROCONF:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            user_input[CONF_HOST] = self.context.get(CONF_HOST)

        errors = {}
        session = async_get_clientsession(self.hass)
        wled = WLED(user_input[CONF_HOST], loop=self.hass.loop, session=session)

        try:
            device = await wled.update()
            mac_address = device.info.mac_address
        except WLEDConnectionError:
            if source == SOURCE_ZEROCONF:
                return self.async_abort(reason="connection_error")
            errors["base"] = "connection_error"
            return await self._show_setup_form(errors)

        # Check if already configured
        for entry in self._async_current_entries():
            if entry.data[CONF_MAC] == mac_address:
                # This mac address is already configured
                return self.async_abort(reason="already_configured")

        title = user_input[CONF_HOST]
        if source == SOURCE_ZEROCONF:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            title = self.context.get(CONF_NAME)

        return self.async_create_entry(
            title=title, data={CONF_HOST: user_input[CONF_HOST], CONF_MAC: mac_address}
        )

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def async_step_zeroconf_confirm(
        self, user_input: ConfigType = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow(user_input)

    async def async_step_zeroconf(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="connection_error")

        # Hostname is format: wled-livingroom.local.
        host = user_input["hostname"].rstrip(".")
        name, _ = host.rsplit(".")

        # Set up connection to WLED to find its unique identifier
        session = async_get_clientsession(self.hass)
        wled = WLED(host, loop=self.hass.loop, session=session)
        try:
            device = await wled.update()
            mac_address = device.info.mac_address
        except WLEDConnectionError:
            return self.async_abort(reason="connection_error")

        # Check if already configured
        for entry in self._async_current_entries():
            if entry.data[CONF_MAC] == mac_address:
                return self.async_abort(reason="already_configured")

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {CONF_HOST: host, CONF_NAME: name, "title_placeholders": {"name": name}}
        )

        return await self.async_step_zeroconf_confirm()

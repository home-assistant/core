"""Config flow to configure the IPP integration."""
import logging
from typing import Any, Dict, Optional

from pyipp import IPP, IPPConnectionError, IPPConnectionUpgradeRequired
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    SOURCE_ZEROCONF,
    ConfigFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BASE_PATH, CONF_UUID
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class IPPFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an IPP config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def async_step_zeroconf(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="connection_error")

        # Hostname is format: EPSON123456.local.
        host = user_input["hostname"].rstrip(".")
        port = user_input["port"]
        name, _ = host.rsplit(".")
        ipp_rp = user_input["properties"].get("rp", "ipp/printer")
        tls = user_input["properties"].get("TLS", "")

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_SSL: tls != "",
                CONF_VERIFY_SSL: False,
                CONF_BASE_PATH: "/" + ipp_rp,
                CONF_NAME: name,
                CONF_UUID: user_input["properties"].get("UUID"),
                "title_placeholders": {"name": name},
            }
        )

        # Prepare configuration flow
        return await self._handle_config_flow(user_input, True)

    async def async_step_zeroconf_confirm(
        self, user_input: ConfigType = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(
        self, user_input: Optional[ConfigType] = None, prepare: bool = False
    ) -> Dict[str, Any]:
        """Config flow handler for IPP."""
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        source = self.context.get("source")

        # Request user input, unless we are preparing discovery flow
        if user_input is None and not prepare:
            if source == SOURCE_ZEROCONF:
                return self._show_confirm_dialog()
            return self._show_setup_form()

        if source == SOURCE_ZEROCONF:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            user_input[CONF_HOST] = self.context.get(CONF_HOST)
            user_input[CONF_PORT] = self.context.get(CONF_PORT)
            user_input[CONF_SSL] = self.context.get(CONF_SSL)
            user_input[CONF_VERIFY_SSL] = self.context.get(CONF_VERIFY_SSL)
            user_input[CONF_BASE_PATH] = self.context.get(CONF_BASE_PATH)
            user_input[CONF_UUID] = self.context.get(CONF_UUID)

        if user_input.get(CONF_UUID) is None or not prepare:
            session = async_get_clientsession(self.hass)
            ipp = IPP(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                base_path=user_input[CONF_BASE_PATH],
                tls=user_input[CONF_SSL],
                verify_ssl=user_input[CONF_VERIFY_SSL],
                session=session,
            )
            try:
                printer = await ipp.printer()
            except IPPConnectionUpgradeRequired:
                if source == SOURCE_ZEROCONF:
                    return self.async_abort(reason="connection_error")
                return self._show_setup_form({"base": "connection_upgrade"})
            except IPPConnectionError:
                if source == SOURCE_ZEROCONF:
                    return self.async_abort(reason="connection_error")
                return self._show_setup_form({"base": "connection_error"})
            user_input[CONF_UUID] = printer.info.uuid

        # Check if already configured
        await self.async_set_unique_id(user_input[CONF_UUID])
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        title = user_input[CONF_HOST]
        if source == SOURCE_ZEROCONF:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            title = self.context.get(CONF_NAME)

        if prepare:
            return await self.async_step_zeroconf_confirm()

        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_SSL: user_input[CONF_SSL],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                CONF_BASE_PATH: user_input[CONF_BASE_PATH],
                CONF_UUID: user_input[CONF_UUID],
            },
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=631): int,
                    vol.Required(CONF_BASE_PATH, default="/ipp/print"): str,
                    vol.Required(CONF_SSL, default=False): bool,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
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

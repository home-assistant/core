"""Config flow to configure the WLED integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from wled import WLED, WLEDConnectionError

from homeassistant.components import zeroconf
from homeassistant.config_entries import (
    SOURCE_ZEROCONF,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_KEEP_MASTER_LIGHT, DEFAULT_KEEP_MASTER_LIGHT, DOMAIN


class WLEDFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a WLED config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WLEDOptionsFlowHandler:
        """Get the options flow for this handler."""
        return WLEDOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        # Hostname is format: wled-livingroom.local.
        host = discovery_info.hostname.rstrip(".")
        name, _ = host.rsplit(".")

        self.context.update(
            {
                CONF_HOST: discovery_info.host,
                CONF_NAME: name,
                CONF_MAC: discovery_info.properties.get(CONF_MAC),
                "title_placeholders": {"name": name},
            }
        )

        # Prepare configuration flow
        return await self._handle_config_flow({}, True)

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(
        self, user_input: dict[str, Any] | None = None, prepare: bool = False
    ) -> FlowResult:
        """Config flow handler for WLED."""
        source = self.context.get("source")

        # Request user input, unless we are preparing discovery flow
        if user_input is None and not prepare:
            if source == SOURCE_ZEROCONF:
                return self._show_confirm_dialog()
            return self._show_setup_form()

        # if prepare is True, user_input can not be None.
        assert user_input is not None

        if source == SOURCE_ZEROCONF:
            user_input[CONF_HOST] = self.context.get(CONF_HOST)
            user_input[CONF_MAC] = self.context.get(CONF_MAC)

        if user_input.get(CONF_MAC) is None or not prepare:
            session = async_get_clientsession(self.hass)
            wled = WLED(user_input[CONF_HOST], session=session)
            try:
                device = await wled.update()
            except WLEDConnectionError:
                if source == SOURCE_ZEROCONF:
                    return self.async_abort(reason="cannot_connect")
                return self._show_setup_form({"base": "cannot_connect"})
            user_input[CONF_MAC] = device.info.mac_address

        # Check if already configured
        await self.async_set_unique_id(user_input[CONF_MAC])
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        title = user_input[CONF_HOST]
        if source == SOURCE_ZEROCONF:
            title = self.context.get(CONF_NAME)

        if prepare:
            return await self.async_step_zeroconf_confirm()

        return self.async_create_entry(
            title=title,
            data={CONF_HOST: user_input[CONF_HOST], CONF_MAC: user_input[CONF_MAC]},
        )

    def _show_setup_form(self, errors: dict | None = None) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    def _show_confirm_dialog(self, errors: dict | None = None) -> FlowResult:
        """Show the confirm dialog to the user."""
        name = self.context.get(CONF_NAME)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": name},
            errors=errors or {},
        )


class WLEDOptionsFlowHandler(OptionsFlow):
    """Handle WLED options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize WLED options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage WLED options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_KEEP_MASTER_LIGHT,
                        default=self.config_entry.options.get(
                            CONF_KEEP_MASTER_LIGHT, DEFAULT_KEEP_MASTER_LIGHT
                        ),
                    ): bool,
                }
            ),
        )

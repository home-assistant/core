"""Config flow for Modern Forms."""

from __future__ import annotations

from typing import Any

from aiomodernforms import ModernFormsConnectionError, ModernFormsDevice
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class ModernFormsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a ModernForms config flow."""

    VERSION = 1

    host: str | None = None
    mac: str | None = None
    name: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup by user for Modern Forms integration."""
        return await self._handle_config_flow(user_input)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.hostname.rstrip(".")
        name, _ = host.rsplit(".")

        self.context["title_placeholders"] = {"name": name}
        self.host = discovery_info.host
        self.mac = discovery_info.properties.get(CONF_MAC)
        self.name = name

        # Prepare configuration flow
        return await self._handle_config_flow({}, True)

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(
        self, user_input: dict[str, Any] | None = None, prepare: bool = False
    ) -> ConfigFlowResult:
        """Config flow handler for ModernForms."""
        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            user_input = {}
            if not prepare:
                if self.source == SOURCE_ZEROCONF:
                    return self.async_show_form(
                        step_id="zeroconf_confirm",
                        description_placeholders={"name": self.name},
                    )
                return self.async_show_form(
                    step_id="user",
                    data_schema=USER_SCHEMA,
                )

        if self.source == SOURCE_ZEROCONF:
            user_input[CONF_HOST] = self.host
            user_input[CONF_MAC] = self.mac

        if user_input.get(CONF_MAC) is None or not prepare:
            session = async_get_clientsession(self.hass)
            device = ModernFormsDevice(user_input[CONF_HOST], session=session)
            try:
                device = await device.update()
            except ModernFormsConnectionError:
                if self.source == SOURCE_ZEROCONF:
                    return self.async_abort(reason="cannot_connect")
                return self.async_show_form(
                    step_id="user",
                    data_schema=USER_SCHEMA,
                    errors={"base": "cannot_connect"},
                )
            user_input[CONF_MAC] = device.info.mac_address

        # Check if already configured
        await self.async_set_unique_id(user_input[CONF_MAC])
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        title = device.info.device_name
        if self.source == SOURCE_ZEROCONF:
            title = self.name

        if prepare:
            return await self.async_step_zeroconf_confirm()

        return self.async_create_entry(
            title=title,
            data={CONF_HOST: user_input[CONF_HOST], CONF_MAC: user_input[CONF_MAC]},
        )

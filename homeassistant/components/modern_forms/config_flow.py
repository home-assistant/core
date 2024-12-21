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

    host: str
    mac: str | None = None
    name: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup by user for Modern Forms integration."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
            )
        self.host = user_input[CONF_HOST]
        return await self._handle_config_flow()

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

        # Loop through self._handle_config_flow to ensure we load the
        # MAC if it is missing, and abort if already configured
        return await self._handle_config_flow(True)

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow()

    async def _handle_config_flow(
        self, initial_zeroconf: bool = False
    ) -> ConfigFlowResult:
        """Config flow handler for ModernForms."""
        if self.mac is None or not initial_zeroconf:
            # User flow
            # Or zeroconf without MAC
            # Or zeroconf with MAC, but need to ensure device is still available
            session = async_get_clientsession(self.hass)
            device = ModernFormsDevice(self.host, session=session)
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
            self.mac = device.info.mac_address
            if self.source != SOURCE_ZEROCONF:
                self.name = device.info.device_name

        # Check if already configured
        await self.async_set_unique_id(self.mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.host})

        if initial_zeroconf:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self.name},
            )

        return self.async_create_entry(
            title=self.name,
            data={CONF_HOST: self.host, CONF_MAC: self.mac},
        )

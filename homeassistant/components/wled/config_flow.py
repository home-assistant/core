"""Config flow to configure the WLED integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from wled import WLED, Device, WLEDConnectionError

from homeassistant.components import onboarding
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_KEEP_MAIN_LIGHT, DEFAULT_KEEP_MAIN_LIGHT, DOMAIN


class WLEDFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a WLED config flow."""

    VERSION = 1
    discovered_host: str
    discovered_device: Device

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> WLEDOptionsFlowHandler:
        """Get the options flow for this handler."""
        return WLEDOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            try:
                device = await self._async_get_device(user_input[CONF_HOST])
            except WLEDConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    device.info.mac_address, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=device.info.name,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        # Abort quick if the mac address is provided by discovery info
        if mac := discovery_info.properties.get(CONF_MAC):
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: discovery_info.host}
            )

        self.discovered_host = discovery_info.host
        try:
            self.discovered_device = await self._async_get_device(discovery_info.host)
        except WLEDConnectionError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self.discovered_device.info.mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.context.update(
            {
                "title_placeholders": {"name": self.discovered_device.info.name},
                "configuration_url": f"http://{discovery_info.host}",
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(
                title=self.discovered_device.info.name,
                data={
                    CONF_HOST: self.discovered_host,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self.discovered_device.info.name},
        )

    async def _async_get_device(self, host: str) -> Device:
        """Get device information from WLED device."""
        session = async_get_clientsession(self.hass)
        wled = WLED(host, session=session)
        return await wled.update()


class WLEDOptionsFlowHandler(OptionsFlow):
    """Handle WLED options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage WLED options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_KEEP_MAIN_LIGHT,
                        default=self.config_entry.options.get(
                            CONF_KEEP_MAIN_LIGHT, DEFAULT_KEEP_MAIN_LIGHT
                        ),
                    ): bool,
                }
            ),
        )

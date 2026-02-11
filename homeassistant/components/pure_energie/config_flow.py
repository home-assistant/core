"""Config flow for Pure Energie integration."""

from __future__ import annotations

from typing import Any

from gridnet import Device, GridNet, GridNetConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN


class PureEnergieFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Pure Energie integration."""

    VERSION = 1
    discovered_host: str
    discovered_device: Device

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}

        if user_input is not None:
            try:
                device = await self._async_get_device(user_input[CONF_HOST])
            except GridNetConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device.n2g_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title="Pure Energie Meter",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): TextSelector(),
                }
            ),
            errors=errors or {},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.discovered_host = discovery_info.host
        try:
            self.discovered_device = await self._async_get_device(discovery_info.host)
        except GridNetConnectionError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self.discovered_device.n2g_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: "Pure Energie Meter",
                    CONF_HOST: self.discovered_host,
                    "model": self.discovered_device.model,
                },
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None:
            return self.async_create_entry(
                title="Pure Energie Meter",
                data={
                    CONF_HOST: self.discovered_host,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                CONF_NAME: "Pure Energie Meter",
                "model": self.discovered_device.model,
            },
        )

    async def _async_get_device(self, host: str) -> Device:
        """Get device information from Pure Energie device."""
        session = async_get_clientsession(self.hass)
        gridnet = GridNet(host, session=session)
        return await gridnet.device()

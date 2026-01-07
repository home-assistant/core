"""Config flow to configure the WLED integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from wled import WLED, Device, WLEDConnectionError, WLEDUnsupportedVersionError
import yarl

from homeassistant.components import onboarding
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_KEEP_MAIN_LIGHT, DEFAULT_KEEP_MAIN_LIGHT, DOMAIN
from .coordinator import WLEDConfigEntry, normalize_mac_address


def _normalize_host(host: str) -> str:
    """Normalize host by extracting hostname if a URL is provided."""
    try:
        return yarl.URL(host).host or host
    except ValueError:
        pass
    return host


class WLEDFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a WLED config flow."""

    VERSION = 1
    MINOR_VERSION = 2
    discovered_host: str
    discovered_device: Device

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: WLEDConfigEntry,
    ) -> WLEDOptionsFlowHandler:
        """Get the options flow for this handler."""
        return WLEDOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            host = _normalize_host(user_input[CONF_HOST])
            try:
                device = await self._async_get_device(host)
            except WLEDUnsupportedVersionError:
                errors["base"] = "unsupported_version"
            except WLEDConnectionError:
                errors["base"] = "cannot_connect"
            else:
                mac_address = normalize_mac_address(device.info.mac_address)
                await self.async_set_unique_id(mac_address, raise_on_progress=False)
                if self.source == SOURCE_RECONFIGURE:
                    entry = self._get_reconfigure_entry()
                    self._abort_if_unique_id_mismatch(
                        reason="unique_id_mismatch",
                        description_placeholders={
                            "expected_mac": format_mac(entry.unique_id).upper(),
                            "actual_mac": mac_address.upper(),
                        },
                    )
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={CONF_HOST: host},
                    )
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=device.info.name,
                    data={CONF_HOST: host},
                )
        data_schema = vol.Schema({vol.Required(CONF_HOST): str})
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                entry.data,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors or {},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow for WLED entry."""
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        # Abort quick if the mac address is provided by discovery info
        if mac := discovery_info.properties.get(CONF_MAC):
            await self.async_set_unique_id(normalize_mac_address(mac))
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: discovery_info.host}
            )

        self.discovered_host = discovery_info.host
        try:
            self.discovered_device = await self._async_get_device(discovery_info.host)
        except WLEDUnsupportedVersionError:
            return self.async_abort(reason="unsupported_version")
        except WLEDConnectionError:
            return self.async_abort(reason="cannot_connect")

        device_mac_address = normalize_mac_address(
            self.discovered_device.info.mac_address
        )
        await self.async_set_unique_id(device_mac_address)
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


class WLEDOptionsFlowHandler(OptionsFlowWithReload):
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

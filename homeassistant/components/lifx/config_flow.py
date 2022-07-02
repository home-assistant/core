"""Config flow flow LIFX."""
from __future__ import annotations

from typing import Any

from aiolifx.aiolifx import Light
from aiolifx.connection import AwaitAioLIFX, LIFXConnection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN, TARGET_ANY
from .discovery import async_discover_devices
from .util import async_entry_is_legacy, get_real_mac_addr, lifx_features


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tplink."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Light] = {}
        self._discovered_device: Light | None = None

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        return await self._async_handle_discovery(
            discovery_info.ip, discovery_info.macaddress
        )

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle HomeKit discovery."""
        return await self._async_handle_discovery(discovery_info.host, None)

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle discovery."""
        return await self._async_handle_discovery(
            discovery_info[CONF_HOST], discovery_info[CONF_MAC]
        )

    async def _async_handle_discovery(self, host: str, mac: str | None) -> FlowResult:
        """Handle any discovery."""
        if mac:
            await self.async_set_unique_id(dr.format_mac(mac))
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")

        device = await self._async_try_connect(host, raise_on_progress=True)
        if not device:
            return self.async_abort(reason="cannot_connect")
        self._discovered_device = device
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        if user_input is not None:
            return self._async_create_entry_from_device(self._discovered_device)

        self._set_confirm_only()
        placeholders = {
            "label": self._discovered_device.label,
            "host": self._discovered_device.ip_addr,
            "mac_addr": self.unique_id,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            if not host:
                return await self.async_step_pick_device()
            if (
                device := await self._async_try_connect(host, raise_on_progress=True)
            ) is None:
                errors["base"] = "cannot_connect"
            else:
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            mac = user_input[CONF_DEVICE]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            device_without_label = self._discovered_devices[mac]
            device = await self._async_try_connect(
                device_without_label.ip_addr, raise_on_progress=False
            )
            if not device:
                return self.async_abort(reason="cannot_connect")
            return self._async_create_entry_from_device(device)

        configured_devices = {
            entry.unique_id
            for entry in self._async_current_entries()
            if not async_entry_is_legacy(entry)
        }
        self._discovered_devices = {
            dr.format_mac(
                get_real_mac_addr(device.mac_addr, device.host_firmware_version)
            ): device
            for device in await async_discover_devices(self.hass)
        }
        devices_name = {
            formatted_mac: f"{formatted_mac} ({device.ip_addr})"
            for formatted_mac, device in self._discovered_devices.items()
            if formatted_mac not in configured_devices
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_migration(self, migration_input: dict[str, Any]) -> FlowResult:
        """Handle migration from legacy config entry to per device config entry."""
        mac = migration_input[CONF_MAC]
        await self.async_set_unique_id(dr.format_mac(mac), raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=migration_input[CONF_NAME],
            data={
                CONF_HOST: migration_input[CONF_HOST],
            },
        )

    @callback
    def _async_create_entry_from_device(self, device: Light) -> FlowResult:
        """Create a config entry from a smart device."""
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.ip_addr})
        return self.async_create_entry(
            title=device.label,
            data={
                CONF_HOST: device.ip_addr,
            },
        )

    async def _async_try_connect(
        self, host: str, raise_on_progress: bool = True
    ) -> Light:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: host})
        connection = LIFXConnection(host, TARGET_ANY)
        await connection.async_setup()
        device: Light = connection.device
        message = await AwaitAioLIFX().wait(device.get_color)
        connection.async_stop()
        if message is None or lifx_features(device)["relays"] is True:
            return None  # relays not supported
        device.mac_addr = message.target_addr
        real_mac = get_real_mac_addr(device.mac_addr, device.host_firmware_version)
        await self.async_set_unique_id(
            dr.format_mac(real_mac), raise_on_progress=raise_on_progress
        )
        return device

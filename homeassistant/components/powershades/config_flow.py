"""Config flow for the PowerShades integration."""

import ipaddress
import logging
from typing import Any

from pyowershades import (
    DiscoveredDevice,
    PowerShadesTimeoutError,
    async_get_device_info,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN
from .discovery import async_discover_devices

_LOGGER = logging.getLogger(__name__)

MANUAL_ENTRY = "manual"


class PowerShadesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a PowerShades config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, DiscoveredDevice] = {}
        self._discovered_ip: str | None = None
        self._discovered_serial: int | None = None
        self._discovered_name: str | None = None
        self._discovered_mac: str | None = None
        self._discovered_model: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: discover devices on the network."""
        discovered = await async_discover_devices(self.hass)
        configured_serials = {
            entry.unique_id
            for entry in self._async_current_entries(include_ignore=False)
            if entry.unique_id is not None
        }
        self._discovered = {
            device["ip"]: device
            for device in discovered
            if str(device["serial"]) not in configured_serials
        }
        if not self._discovered:
            return await self.async_step_manual()
        return await self.async_step_pick_device()

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            choice = user_input["device"]
            if choice == MANUAL_ENTRY:
                return await self.async_step_manual()
            result = await self._async_validate_and_create(choice, errors)
            if result is not None:
                return result

        choices = {
            ip: f"{ip} (Serial: {device['serial']})"
            for ip, device in self._discovered.items()
        }
        choices[MANUAL_ENTRY] = "Enter IP address manually"

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required("device"): vol.In(choices)}),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            ip = user_input["ip"].strip()
            try:
                ipaddress.IPv4Address(ip)
            except ValueError:
                errors["ip"] = "invalid_ip"
            else:
                result = await self._async_validate_and_create(ip, errors)
                if result is not None:
                    return result

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required("ip"): str}),
            errors=errors,
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a device found by background broadcast discovery."""
        self._discovered_model = discovery_info.get("model")
        return await self._async_handle_discovery(
            discovery_info["ip"], discovery_info["serial"]
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a device found by DHCP discovery."""
        ip = discovery_info.ip
        self._discovered_mac = format_mac(discovery_info.macaddress)
        # The DHCP matcher is assumes the mac address and hostname may be a Powershade; verify
        # the device actually speaks the PowerShades protocol.
        try:
            info = await async_get_device_info(ip)
        except PowerShadesTimeoutError:
            return self.async_abort(reason="cannot_connect")
        self._discovered_name = info["name"]
        self._discovered_model = info["model"]
        return await self._async_handle_discovery(ip, info["serial"])

    async def _async_handle_discovery(self, ip: str, serial: int) -> ConfigFlowResult:
        """Common handling for discovered devices."""
        await self.async_set_unique_id(str(serial))
        updates = {"ip": ip}
        if self._discovered_mac:
            updates["mac"] = self._discovered_mac
        self._abort_if_unique_id_configured(updates=updates)

        self._discovered_ip = ip
        self._discovered_serial = serial
        if self._discovered_name is None:
            try:
                info = await async_get_device_info(ip)
                self._discovered_name = info["name"]
                if self._discovered_model is None:
                    self._discovered_model = info["model"]
            except PowerShadesTimeoutError:
                self._discovered_name = None

        self.context["title_placeholders"] = {
            "name": self._discovered_name or ip,
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered device."""
        if user_input is not None:
            ip = self._discovered_ip
            name = self._discovered_name
            title = f"PowerShade {name}" if name else f"PowerShade {ip}"
            return self.async_create_entry(
                title=title,
                data={
                    "ip": ip,
                    "serial": self._discovered_serial,
                    "name": name,
                    "mac": self._discovered_mac,
                    "model": self._discovered_model,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._discovered_name or "PowerShades device",
                "ip": self._discovered_ip or "",
            },
        )

    async def _async_validate_and_create(
        self, ip: str, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Probe the device and create the entry, or record an error."""
        try:
            info = await async_get_device_info(ip)
        except PowerShadesTimeoutError:
            _LOGGER.debug("Device at %s did not respond to probe", ip)
            errors["base"] = "cannot_connect"
            return None

        await self.async_set_unique_id(str(info["serial"]))
        self._abort_if_unique_id_configured(updates={"ip": ip})

        name = info["name"]
        title = f"PowerShade {name}" if name else f"PowerShade {ip}"
        return self.async_create_entry(
            title=title,
            data={
                "ip": ip,
                "serial": info["serial"],
                "name": name,
                "model": info["model"],
            },
        )

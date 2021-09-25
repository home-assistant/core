"""Config flow for TP-Link."""
from __future__ import annotations

import logging

from kasa import SmartDevice, SmartDeviceException
from kasa.discover import Discover
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import IP_ADDRESS, MAC_ADDRESS
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_LEGACY_ENTRY_ID, DISCOVERED_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tplink."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, SmartDevice] = {}
        self._discovered_device: SmartDevice | None = None
        self._discovered_ip: str | None = None

    async def async_step_dhcp(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle discovery via dhcp."""
        self.context[CONF_HOST] = self._discovered_ip = discovery_info[IP_ADDRESS]
        await self.async_set_unique_id(dr.format_mac(discovery_info[MAC_ADDRESS]))
        return await self._async_handle_discovery()

    async def async_step_discovery(self, discovery_info) -> FlowResult:
        """Handle discovery."""
        self.context[CONF_HOST] = self._discovered_ip = discovery_info[CONF_HOST]
        await self.async_set_unique_id(dr.format_mac(discovery_info[CONF_MAC]))
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> FlowResult:
        """Handle any discovery."""
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._discovered_ip})
        self._async_abort_entries_match({CONF_HOST: self._discovered_ip})
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self._discovered_ip:
                return self.async_abort(reason="already_in_progress")

        try:
            self._discovered_device = await self._async_try_connect(
                self._discovered_ip, raise_on_progress=True
            )
        except SmartDeviceException:
            return self.async_abort(reason="cannot_connect")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        if user_input is not None:
            return self.async_create_entry(
                title=f"{self._discovered_device.alias} {self._discovered_device.model}",
                data={
                    CONF_HOST: self._discovered_ip,
                },
            )

        self._set_confirm_only()
        placeholders = {
            "name": self._discovered_device.alias,
            "model": self._discovered_device.model,
            "host": self._discovered_ip,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_HOST):
                return await self.async_step_pick_device()
            try:
                device = await self._async_try_connect(
                    user_input[CONF_HOST], raise_on_progress=False
                )
            except SmartDeviceException:
                errors["base"] = "cannot_connect"
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{device.alias} {device.model}",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Optional(CONF_HOST, default=user_input.get(CONF_HOST, "")): str}
            ),
            errors=errors,
        )

    async def async_step_pick_device(self, user_input=None) -> FlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            device_id: str = user_input[CONF_DEVICE]
            mac = device_id.split(" ")[-1]
            device: SmartDevice = self._discovered_devices[mac]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{device.alias} {device.model}",
                data={
                    CONF_HOST: device.host,
                },
            )

        configured_devices = {
            entry.unique_id
            for entry in self._async_current_entries()
            if entry.unique_id
        }
        self._discovered_devices = {
            dr.format_mac(device.mac): device
            for device in (await Discover.discover()).values()
        }
        devices_name = {
            f"{device.alias} {device.model} ({device.host}) {formatted_mac}"
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

    async def async_step_migration(self, migration_input=None) -> FlowResult:
        """Handle migration from legacy config entry to per device config entry."""
        mac = migration_input[CONF_MAC]
        name = migration_input[CONF_NAME]
        discovered_devices = self.hass.data[DOMAIN][DISCOVERED_DEVICES]
        host = None
        if device := discovered_devices.get(mac):
            host = device.host
        await self.async_set_unique_id(dr.format_mac(mac), raise_on_progress=True)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: host,
                CONF_LEGACY_ENTRY_ID: migration_input[CONF_LEGACY_ENTRY_ID],
            },
        )

    async def async_step_import(self, user_input=None) -> FlowResult:
        """Handle import step."""
        host = user_input[CONF_HOST]
        try:
            device = await self._async_try_connect(host, raise_on_progress=False)
        except SmartDeviceException:
            _LOGGER.error("Failed to import %s: cannot connect", host)
            return self.async_abort(reason="cannot_connect")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{device.alias} {device.model}",
            data={
                CONF_HOST: device.host,
            },
        )

    async def _async_try_connect(self, host, raise_on_progress=True) -> SmartDevice:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: host})
        device: SmartDevice = await Discover.discover_single(host)
        await self.async_set_unique_id(
            dr.format_mac(device.mac), raise_on_progress=raise_on_progress
        )
        return device

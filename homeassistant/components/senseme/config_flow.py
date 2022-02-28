"""Config flow for SenseME."""
from __future__ import annotations

import ipaddress
from typing import Any

from aiosenseme import SensemeDevice, async_get_device_by_ip_address
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_ID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_HOST_MANUAL, CONF_INFO, DOMAIN
from .discovery import async_discover, async_get_discovered_device

DISCOVER_TIMEOUT = 5


class SensemeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle SenseME discovery config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the SenseME config flow."""
        self._discovered_devices: list[SensemeDevice] | None = None
        self._discovered_device: SensemeDevice | None = None

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        # If discovery is already running, it takes precedence since its more efficient
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if device := await async_get_device_by_ip_address(discovery_info.ip):
            device.stop()
        if device is None or not device.uuid:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(device.uuid)
        self._discovered_device = device
        return await self.async_step_discovery_confirm()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle integration discovery."""
        uuid = discovery_info[CONF_ID]
        device = async_get_discovered_device(self.hass, discovery_info[CONF_ID])
        host = device.address
        await self.async_set_unique_id(uuid)
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_INFO]["address"] == host:
                return self.async_abort(reason="already_configured")
            if entry.unique_id != uuid:
                continue
            self.hass.config_entries.async_update_entry(
                entry, data={CONF_INFO: {**entry.data[CONF_INFO], "address": host}}
            )
            return self.async_abort(reason="already_configured")
        self._discovered_device = device
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        device = self._discovered_device
        assert device is not None

        if user_input is not None:
            return await self._async_entry_for_device(device)
        placeholders = {
            "name": device.name,
            "model": device.model,
            "host": device.address,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def _async_entry_for_device(self, device: SensemeDevice) -> FlowResult:
        """Create a config entry for a device."""
        await self.async_set_unique_id(device.uuid, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=device.name,
            data={CONF_INFO: device.get_device_info},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual entry of an ip address."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                ipaddress.ip_address(host)
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                if device := await async_get_device_by_ip_address(host):
                    device.stop()
                    return await self._async_entry_for_device(device)

                errors[CONF_HOST] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._discovered_devices is None:
            self._discovered_devices = await async_discover(self.hass, DISCOVER_TIMEOUT)
        current_ids = self._async_current_ids()
        device_selection = {
            device.uuid: device.name
            for device in self._discovered_devices
            if device.uuid not in current_ids
        }

        if not device_selection:
            return await self.async_step_manual(user_input=None)

        device_selection[None] = CONF_HOST_MANUAL

        if user_input is not None:
            if user_input[CONF_DEVICE] is None:
                return await self.async_step_manual()

            for device in self._discovered_devices:
                if device.uuid == user_input[CONF_DEVICE]:
                    return await self._async_entry_for_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE): vol.In(device_selection)}
            ),
        )

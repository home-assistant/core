"""Config flow for SenseME."""
from __future__ import annotations

import ipaddress
from typing import Any

from aiosenseme import SensemeDevice, async_get_device_by_ip_address, discover_all
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_HOST_MANUAL, CONF_INFO, DOMAIN

DISCOVER_TIMEOUT = 5


class SensemeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle SenseME discovery config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the SenseME config flow."""
        self._discovered_devices: list[SensemeDevice] | None = None
        self._discovered_device: SensemeDevice | None = None

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle discovery."""
        self._discovered_device = discovery_info
        host = discovery_info[CONF_HOST]
        await self.async_set_unique_id(discovery_info[CONF_ID])
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_INFO]["address"] == host:
                return self.async_abort(reason="already_configured")
            if entry.unique_id != discovery_info[CONF_ID]:
                continue
            if entry.data[CONF_INFO]["address"] != host:
                self.hass.config_entries.async_update_entry(
                    entry, data={CONF_INFO: {**entry.data[CONF_INFO], "address": host}}
                )
            return self.async_abort(reason="already_configured")
        if not (device := await async_get_device_by_ip_address(host)):
            return self.async_abort(reason="cannot_connect")
        device.stop()
        self._discovered_device = device
        self._set_confirm_only()
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        device = self._discovered_device
        assert device is not None

        if user_input is not None:
            return await self._async_entry_for_device(device)
        placeholders = {"model": device.model, "host": device.address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def _async_entry_for_device(self, device: SensemeDevice) -> FlowResult:
        """Create a config entry for a device."""
        await self.async_set_unique_id(device.uuid)
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
        # start discovery the first time through
        if self._discovered_devices is None:
            self._discovered_devices = await discover_all(DISCOVER_TIMEOUT)

        current_ids = self._async_current_ids()
        device_selection = [
            device.name
            for device in self._discovered_devices
            if device.uuid not in current_ids
        ]

        if not device_selection:
            return await self.async_step_manual(user_input=None)

        device_selection.append(CONF_HOST_MANUAL)

        if user_input is not None:
            if user_input[CONF_HOST] == CONF_HOST_MANUAL:
                return await self.async_step_manual()

            for device in self._discovered_devices:
                if device == user_input[CONF_HOST]:
                    return await self._async_entry_for_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=device_selection[0]): vol.In(
                        device_selection
                    )
                }
            ),
        )

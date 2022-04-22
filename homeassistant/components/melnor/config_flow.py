"""Config flow for melnor."""

from __future__ import annotations

from typing import Any

from melnor_bluetooth.device import Device
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_MAC
from homeassistant.data_entry_flow import FlowResult

from .const import DISCOVER_SCAN_TIMEOUT, DOMAIN
from .discovery import async_discover_devices


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for melnor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: Device
        self._discovered_devices: dict[str, Device]

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to pick discovered device."""

        if user_input is not None:
            device = self._discovered_devices[user_input[CONF_MAC]]

            await self.async_set_unique_id(device.mac, raise_on_progress=False)
            return self.async_create_entry(
                title=device.mac,
                data={
                    CONF_MAC: device.mac,
                },
            )

        current_unique_ids = self._async_current_ids()
        current_devices = {
            entry.data[CONF_MAC]
            for entry in self._async_current_entries(include_ignore=False)
        }

        self._discovered_devices = await async_discover_devices(DISCOVER_SCAN_TIMEOUT)

        device_macs = {
            mac
            for mac in self._discovered_devices.keys()
            if mac not in current_unique_ids and mac not in current_devices
        }

        if len(device_macs) == 1:
            mac = next(iter(device_macs))
            return await self.async_step_pick_device({CONF_MAC: mac})

        # Check if there is at least one device
        if not device_macs:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_MAC): vol.In(device_macs)}),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_pick_device()

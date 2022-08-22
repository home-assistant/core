"""Config flow for Airthings BlE integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AirthingsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airthings BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: BluetoothServiceInfo | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfo] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered BT device: %s", discovery_info)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        if 820 not in discovery_info.manufacturer_data:
            return self.async_abort(reason="not_supported")

        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        self._discovered_device = discovery_info

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            return self._async_get_or_create_entry(scan_interval)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): int,
                },
            ),
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]

            self.context["title_placeholders"] = {
                "name": discovery.name or discovery.address
            }

            self._discovered_device = discovery

            return self._async_get_or_create_entry(scan_interval)

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if (
                address in current_addresses
                or address in self._discovered_devices
            ):
                continue

            if 820 not in discovery_info.manufacturer_data:
                continue

            self._discovered_devices[address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: discovery.address
            for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(titles),
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): int,
                },
            ),
        )

    def _async_get_or_create_entry(self, scan_interval: int):
        data = {CONF_SCAN_INTERVAL: scan_interval}

        if entry_id := self.context.get("entry_id"):
            entry = self.hass.config_entries.async_get_entry(entry_id)
            assert entry is not None

            self.hass.config_entries.async_update_entry(entry, data=data)

            # Reload the config entry to notify of updated config
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=self.context["title_placeholders"]["name"],
            data=data,
        )

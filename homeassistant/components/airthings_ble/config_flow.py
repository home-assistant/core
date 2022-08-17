"""Config flow for Xiaomi Bluetooth integration."""
from __future__ import annotations

import dataclasses
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

# How long to wait for additional advertisement packets if we don't have the right ones
ADDITIONAL_DISCOVERY_TIMEOUT = 60

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class Discovery:
    """A discovered bluetooth device."""

    title: str
    discovery_info: BluetoothServiceInfo
    device: None


class AirthingsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airthings Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfo | None = None
        self._discovered_device: None | None = None
        self._discovered_devices: dict[str, Discovery] = {}

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
        self._discovered_device = None

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self._async_get_or_create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]

            self.context["title_placeholders"] = {"name": discovery.title}

            self._discovered_device = discovery.device

            return self._async_get_or_create_entry()

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = None

            if 820 not in discovery_info.manufacturer_data:
                continue

            self._discovered_devices[address] = Discovery(
                title=discovery_info.name or discovery_info.address,
                discovery_info=discovery_info,
                device=device,
            )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: discovery.title
            for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )

    def _async_get_or_create_entry(self, bindkey=None):
        data = {}

        if bindkey:
            data["bindkey"] = bindkey

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

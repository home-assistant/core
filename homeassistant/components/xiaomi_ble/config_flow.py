"""Config flow for Xiaomi Bluetooth integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import dataclasses
from typing import Any

import voluptuous as vol
from xiaomi_ble import XiaomiBluetoothDeviceData as DeviceData
from xiaomi_ble.parser import EncryptionScheme

from homeassistant.components import onboarding
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

# How long to wait for additional advertisement packets if we don't have the right ones
ADDITIONAL_DISCOVERY_TIMEOUT = 60


@dataclasses.dataclass
class Discovery:
    """A discovered bluetooth device."""

    title: str
    discovery_info: BluetoothServiceInfo
    device: DeviceData


def _title(discovery_info: BluetoothServiceInfo, device: DeviceData) -> str:
    return device.title or device.get_device_name() or discovery_info.name


class XiaomiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Xiaomi Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfo | None = None
        self._discovered_device: DeviceData | None = None
        self._discovered_devices: dict[str, Discovery] = {}

    async def _async_wait_for_full_advertisement(
        self, discovery_info: BluetoothServiceInfo, device: DeviceData
    ) -> BluetoothServiceInfo:
        """Sometimes first advertisement we receive is blank or incomplete.

        Wait until we get a useful one.
        """
        if not device.pending:
            return discovery_info

        def _process_more_advertisements(
            service_info: BluetoothServiceInfo,
        ) -> bool:
            device.update(service_info)
            return not device.pending

        return await async_process_advertisements(
            self.hass,
            _process_more_advertisements,
            {"address": discovery_info.address},
            BluetoothScanningMode.ACTIVE,
            ADDITIONAL_DISCOVERY_TIMEOUT,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = DeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")

        title = _title(discovery_info, device)
        self.context["title_placeholders"] = {"name": title}

        self._discovered_device = device

        # Wait until we have received enough information about
        # this device to detect its encryption type
        try:
            self._discovery_info = await self._async_wait_for_full_advertisement(
                discovery_info, device
            )
        except asyncio.TimeoutError:
            # This device might have a really long advertising interval
            # So create a config entry for it, and if we discover it has
            # encryption later, we can do a reauth
            return await self.async_step_confirm_slow()

        if device.encryption_scheme == EncryptionScheme.MIBEACON_LEGACY:
            return await self.async_step_get_encryption_key_legacy()
        if device.encryption_scheme == EncryptionScheme.MIBEACON_4_5:
            return await self.async_step_get_encryption_key_4_5()
        return await self.async_step_bluetooth_confirm()

    async def async_step_get_encryption_key_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter a legacy bindkey for a v2/v3 MiBeacon device."""
        assert self._discovery_info
        assert self._discovered_device

        errors = {}

        if user_input is not None:
            bindkey = user_input["bindkey"]

            if len(bindkey) != 24:
                errors["bindkey"] = "expected_24_characters"
            else:
                self._discovered_device.bindkey = bytes.fromhex(bindkey)

                # If we got this far we already know supported will
                # return true so we don't bother checking that again
                # We just want to retry the decryption
                self._discovered_device.supported(self._discovery_info)

                if self._discovered_device.bindkey_verified:
                    return self._async_get_or_create_entry(bindkey)

                errors["bindkey"] = "decryption_failed"

        return self.async_show_form(
            step_id="get_encryption_key_legacy",
            description_placeholders=self.context["title_placeholders"],
            data_schema=vol.Schema({vol.Required("bindkey"): vol.All(str, vol.Strip)}),
            errors=errors,
        )

    async def async_step_get_encryption_key_4_5(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter a bindkey for a v4/v5 MiBeacon device."""
        assert self._discovery_info
        assert self._discovered_device

        errors = {}

        if user_input is not None:
            bindkey = user_input["bindkey"]

            if len(bindkey) != 32:
                errors["bindkey"] = "expected_32_characters"
            else:
                self._discovered_device.bindkey = bytes.fromhex(bindkey)

                # If we got this far we already know supported will
                # return true so we don't bother checking that again
                # We just want to retry the decryption
                self._discovered_device.supported(self._discovery_info)

                if self._discovered_device.bindkey_verified:
                    return self._async_get_or_create_entry(bindkey)

                errors["bindkey"] = "decryption_failed"

        return self.async_show_form(
            step_id="get_encryption_key_4_5",
            description_placeholders=self.context["title_placeholders"],
            data_schema=vol.Schema({vol.Required("bindkey"): vol.All(str, vol.Strip)}),
            errors=errors,
        )

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

    async def async_step_confirm_slow(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ack that device is slow."""
        if user_input is not None:
            return self._async_get_or_create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm_slow",
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

            # Wait until we have received enough information about
            # this device to detect its encryption type
            try:
                self._discovery_info = await self._async_wait_for_full_advertisement(
                    discovery.discovery_info, discovery.device
                )
            except asyncio.TimeoutError:
                # This device might have a really long advertising interval
                # So create a config entry for it, and if we discover
                # it has encryption later, we can do a reauth
                return await self.async_step_confirm_slow()

            self._discovered_device = discovery.device

            if discovery.device.encryption_scheme == EncryptionScheme.MIBEACON_LEGACY:
                return await self.async_step_get_encryption_key_legacy()

            if discovery.device.encryption_scheme == EncryptionScheme.MIBEACON_4_5:
                return await self.async_step_get_encryption_key_4_5()

            return self._async_get_or_create_entry()

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = DeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = Discovery(
                    title=_title(discovery_info, device),
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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a flow initialized by a reauth event."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        device: DeviceData = entry_data["device"]
        self._discovered_device = device

        self._discovery_info = device.last_service_info

        if device.encryption_scheme == EncryptionScheme.MIBEACON_LEGACY:
            return await self.async_step_get_encryption_key_legacy()

        if device.encryption_scheme == EncryptionScheme.MIBEACON_4_5:
            return await self.async_step_get_encryption_key_4_5()

        # Otherwise there wasn't actually encryption so abort
        return self.async_abort(reason="reauth_successful")

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

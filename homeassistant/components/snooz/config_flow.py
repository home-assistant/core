"""Config flow for Snooz component."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pysnooz.advertisement import SnoozAdvertisementData
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TOKEN

from .const import DOMAIN

# number of seconds to wait for a device to be put in pairing mode
WAIT_FOR_PAIRING_TIMEOUT = 30


@dataclass
class DiscoveredSnooz:
    """Represents a discovered Snooz device."""

    info: BluetoothServiceInfo
    device: SnoozAdvertisementData


class SnoozConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Snooz."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery: DiscoveredSnooz | None = None
        self._discovered_devices: dict[str, DiscoveredSnooz] = {}
        self._pairing_task: asyncio.Task | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = SnoozAdvertisementData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery = DiscoveredSnooz(discovery_info, device)
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery is not None

        if user_input is not None:
            if not self._discovery.device.is_pairing:
                return await self.async_step_wait_for_pairing_mode()

            return self._create_snooz_entry(self._discovery)

        self._set_confirm_only()
        assert self._discovery.device.display_name
        placeholders = {"name": self._discovery.device.display_name}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            name = user_input[CONF_NAME]

            discovered = self._discovered_devices[name]

            assert discovered is not None

            self._discovery = discovered

            if not discovered.device.is_pairing:
                return await self.async_step_wait_for_pairing_mode()

            address = discovered.info.address
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self._create_snooz_entry(discovered)

        configured_addresses = self._async_current_ids()

        for info in async_discovered_service_info(self.hass):
            address = info.address
            if address in configured_addresses:
                continue
            device = SnoozAdvertisementData()
            if device.supported(info):
                assert device.display_name
                self._discovered_devices[device.display_name] = DiscoveredSnooz(
                    info, device
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): vol.In(
                        [
                            d.device.display_name
                            for d in self._discovered_devices.values()
                        ]
                    )
                }
            ),
        )

    async def async_step_wait_for_pairing_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for device to enter pairing mode."""
        if not self._pairing_task:
            self._pairing_task = self.hass.async_create_task(
                self._async_wait_for_pairing_mode()
            )

        if not self._pairing_task.done():
            return self.async_show_progress(
                step_id="wait_for_pairing_mode",
                progress_action="wait_for_pairing_mode",
                progress_task=self._pairing_task,
            )

        try:
            await self._pairing_task
        except TimeoutError:
            return self.async_show_progress_done(next_step_id="pairing_timeout")
        finally:
            self._pairing_task = None

        return self.async_show_progress_done(next_step_id="pairing_complete")

    async def async_step_pairing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a configuration entry for a device that entered pairing mode."""
        assert self._discovery

        await self.async_set_unique_id(
            self._discovery.info.address, raise_on_progress=False
        )
        self._abort_if_unique_id_configured()

        return self._create_snooz_entry(self._discovery)

    async def async_step_pairing_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Inform the user that the device never entered pairing mode."""
        if user_input is not None:
            return await self.async_step_wait_for_pairing_mode()

        self._set_confirm_only()
        return self.async_show_form(step_id="pairing_timeout")

    def _create_snooz_entry(self, discovery: DiscoveredSnooz) -> ConfigFlowResult:
        assert discovery.device.display_name
        return self.async_create_entry(
            title=discovery.device.display_name,
            data={
                CONF_ADDRESS: discovery.info.address,
                CONF_TOKEN: discovery.device.pairing_token,
            },
        )

    async def _async_wait_for_pairing_mode(self) -> None:
        """Process advertisements until pairing mode is detected."""
        assert self._discovery
        device = self._discovery.device

        def is_device_in_pairing_mode(
            service_info: BluetoothServiceInfo,
        ) -> bool:
            return device.supported(service_info) and device.is_pairing

        await async_process_advertisements(
            self.hass,
            is_device_in_pairing_mode,
            {"address": self._discovery.info.address},
            BluetoothScanningMode.ACTIVE,
            WAIT_FOR_PAIRING_TIMEOUT,
        )

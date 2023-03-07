"""Config flow for Ooler Sleep System integration."""
from __future__ import annotations

import asyncio
from typing import Any

from bleak.backends.device import BLEDevice
from ooler_ble_client import OolerBLEDevice, test_connection
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
    async_last_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS  # , CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_MODEL, DOMAIN  # , _LOGGER


class OolerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ooler."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}
        self._pairing_task: asyncio.Task | None = None
        self._paired: bool = False
        self._bledevice: BLEDevice | None = None
        self._client: OolerBLEDevice | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not discovery_info.name.startswith("OOLER"):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info

        model_name = discovery_info.name
        assert model_name is not None

        if user_input is not None:
            if not self._paired:
                return await self.async_step_wait_for_pairing_mode()
            return self._create_ooler_entry(model_name)

        self._set_confirm_only()
        placeholders = {"name": model_name}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            model_name = self._discovered_devices[address]
            if model_name is None:
                return self.async_abort(reason="no_devices_found")

            discovery_info = async_last_service_info(
                self.hass, address, connectable=True
            )
            self._discovery_info = discovery_info

            if not self._paired:
                return await self.async_step_wait_for_pairing_mode()
            return self._create_ooler_entry(model_name)

        configured_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if (
                address in configured_addresses
                or address in self._discovered_devices
                or not discovery_info.name.startswith("OOLER")
            ):
                continue
            self._discovered_devices[address] = discovery_info.name

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )

    async def async_step_wait_for_pairing_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Wait for device to enter pairing mode."""
        if not self._pairing_task:
            discovery_info = self._discovery_info
            if discovery_info is None:
                return self.async_show_progress_done(next_step_id="pairing_timeout")
            bledevice = discovery_info.device
            self._pairing_task = self.hass.async_create_task(
                self._async_check_ooler_connection(bledevice)
            )
            return self.async_show_progress(
                step_id="wait_for_pairing_mode",
                progress_action="wait_for_pairing_mode",
            )
        try:
            await self._pairing_task
        except asyncio.CancelledError:
            self._pairing_task = None
            return self.async_show_progress_done(next_step_id="pairing_timeout")
        self._pairing_task = None
        return self.async_show_progress_done(next_step_id="pairing_complete")

    async def async_step_pairing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create a configuration entry for a device that entered pairing mode."""
        assert self._discovery_info
        model_name = self._discovery_info.name

        await self.async_set_unique_id(
            self._discovery_info.address, raise_on_progress=False
        )
        self._abort_if_unique_id_configured()

        return self._create_ooler_entry(model_name)

    async def async_step_pairing_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Inform the user that the device never entered pairing mode."""
        if user_input is not None:
            return await self.async_step_wait_for_pairing_mode()

        self._set_confirm_only()
        return self.async_show_form(step_id="pairing_timeout")

    def _create_ooler_entry(self, model_name: str) -> FlowResult:
        return self.async_create_entry(
            title=model_name,
            data={CONF_MODEL: model_name},  # could require discovery_info.name instead
        )

    # async def _async_wait_for_pairing_mode(self) -> None:
    #     """Process advertisements until pairing mode is detected."""
    #     in_pairing_mode: Future[bool] = Future()

    #     async def device_in_pairing_mode(
    #         device: BLEDevice,
    #         advertisement_data: AdvertisementData,
    #     ):
    #         assert self._discovery_info is not None
    #         if device.address == self._discovery_info.address:
    #             in_pairing_mode.set_result(True)

    #     pairing_scanner = BleakScanner(
    #         device_in_pairing_mode,
    #         scanning_mode="passive",
    #         bluez=BlueZScannerArgs(
    #             or_patterns=[OrPattern(0, AdvertisementDataType.FLAGS, b"\x02")]
    #         ),
    #     )

    #     try:
    #         _LOGGER.error("Starting Ooler scanner")
    #         result = await pairing_scanner.start()
    #         _LOGGER.error("Result of scanner start is: %s", result)
    #         await asyncio.sleep(ADDITIONAL_DISCOVERY_TIMEOUT)
    #         # _LOGGER.error("Scanner: ", pairing_scanner)
    #         _LOGGER.error("Stopping Ooler scanner")
    #         await pairing_scanner.stop()
    #         raise asyncio.TimeoutError

    #     finally:
    #         self.hass.async_create_task(
    #             self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
    #         )

    async def _async_check_ooler_connection(self, bledevice: BLEDevice) -> None:  #
        """Try to connect to client and test read and write power functions to test if paired."""
        await asyncio.sleep(5)
        assert self._pairing_task is not None
        try:
            await test_connection(bledevice)
        except Exception:  # pylint: disable=broad-except
            self._pairing_task.cancel()
        else:
            self._paired = True
        finally:
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
            )

"""Config flow for RYSE BLE integration."""

import logging
from typing import Any, override

from bleak import BleakError
from ryseble import is_pairing_mode
from ryseble.device import RyseBLEDevice
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothScannerDevice,
    BluetoothServiceInfoBleak,
    async_clear_address_from_match_history,
    async_discovered_service_info,
    async_last_service_info,
    async_scanner_by_source,
    async_scanner_devices_by_address,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RyseBLEDeviceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for RYSE BLE Device."""

    def __init__(self) -> None:
        """Initialize flow attributes."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    def _latest_service_info(
        self, service_info: BluetoothServiceInfoBleak
    ) -> BluetoothServiceInfoBleak:
        """Return the freshest advertisement for this address, if any."""
        return (
            async_last_service_info(self.hass, service_info.address, connectable=True)
            or service_info
        )

    def _is_remote_source(self, source: str) -> bool:
        """Return True if *source* is a Bluetooth proxy scanner."""
        return isinstance(
            async_scanner_by_source(self.hass, source), BaseHaRemoteScanner
        )

    def _local_scanner_device(self, address: str) -> BluetoothScannerDevice | None:
        """Return a local-adapter scanner device for *address*, if any."""
        for scanner_device in async_scanner_devices_by_address(
            self.hass, address, connectable=True
        ):
            if not isinstance(scanner_device.scanner, BaseHaRemoteScanner):
                return scanner_device
        return None

    def _with_local_device(
        self,
        service_info: BluetoothServiceInfoBleak,
        scanner_device: BluetoothScannerDevice,
    ) -> BluetoothServiceInfoBleak:
        """Copy *service_info* onto the local adapter's BLEDevice."""
        return BluetoothServiceInfoBleak(
            name=service_info.name,
            address=service_info.address,
            rssi=service_info.rssi,
            manufacturer_data=service_info.manufacturer_data,
            service_data=service_info.service_data,
            service_uuids=service_info.service_uuids,
            source=scanner_device.scanner.source,
            device=scanner_device.ble_device,
            advertisement=service_info.advertisement,
            time=service_info.time,
            connectable=True,
            tx_power=service_info.tx_power,
        )

    def _local_service_info(
        self,
        service_info: BluetoothServiceInfoBleak,
        *,
        prefer_pairing: bool = False,
    ) -> BluetoothServiceInfoBleak | None:
        """Return a local-adapter advertisement, ignoring Bluetooth proxies.

        ``async_last_service_info`` / ``async_discovered_service_info`` expose
        only the Bluetooth manager's selected route. A stronger proxy can win
        that selection even when a local adapter also sees the shade. Check
        every scanner before treating the device as proxy-only.
        """
        latest = self._latest_service_info(service_info)
        candidates: list[BluetoothServiceInfoBleak] = []
        for info in (latest, service_info):
            if info not in candidates:
                candidates.append(info)

        local = [info for info in candidates if not self._is_remote_source(info.source)]
        if not local:
            scanner_device = self._local_scanner_device(service_info.address)
            if scanner_device is None:
                return None
            pairing_info = next(
                (
                    info
                    for info in candidates
                    if is_pairing_mode(info.manufacturer_data)
                ),
                candidates[0],
            )
            local = [self._with_local_device(pairing_info, scanner_device)]
        if prefer_pairing:
            for info in local:
                if is_pairing_mode(info.manufacturer_data):
                    return info
        return local[0]

    async def _async_pair(self, service_info: BluetoothServiceInfoBleak) -> str | None:
        """Bond with the device via Bleak, then release the connection.

        Returns an error key, or None on success. Pairing is refused unless the
        latest advertisement still has the PAIR flag set and came from a local
        adapter; ryseble's BlueZ agent cannot pair through a Bluetooth proxy.
        """
        latest = self._local_service_info(service_info)
        if latest is None:
            return "not_local_source"
        if not is_pairing_mode(latest.manufacturer_data):
            return "not_in_pairing_mode"

        device = RyseBLEDevice(latest.device)
        try:
            if await device.pair():
                return None
        except TimeoutError, OSError, EOFError, BleakError:
            _LOGGER.error("Connection error during pairing")
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during pairing")
            return "unexpected_error"
        finally:
            await device.unpair()
        return "cannot_connect"

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        latest = self._local_service_info(discovery_info, prefer_pairing=True)
        if latest is None:
            # Release the unique id so a later PAIR advertisement can start a
            # new flow instead of aborting as already_in_progress.
            await self.async_set_unique_id(None)
            async_clear_address_from_match_history(self.hass, discovery_info.address)
            return self.async_abort(reason="not_local_source")
        if not is_pairing_mode(latest.manufacturer_data):
            # Idle shades still match the manifest; drop them here so they are
            # not shown as unusable discoveries. Clear matcher history so a
            # later PAIR-flag advertisement can start a new flow.
            await self.async_set_unique_id(None)
            async_clear_address_from_match_history(self.hass, discovery_info.address)
            return self.async_abort(reason="not_in_pairing_mode")

        self._discovery_info = latest

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered BLE device."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        name = discovery_info.name or "RYSE device"

        errors: dict[str, str] = {}

        if user_input is not None:
            if error := await self._async_pair(discovery_info):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=name,
                    data={},
                )

        self._set_confirm_only()
        self.context["title_placeholders"] = {"name": name}
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual 'Add Integration'."""

        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            service_info = self._discovered_devices[address]

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            if error := await self._async_pair(service_info):
                errors["base"] = error
            else:
                return self.async_create_entry(title=service_info.name, data={})

        if user_input is None:
            current_ids = self._async_current_ids(include_ignore=False)

            # A device only sets the pairing flag in its manufacturer data while
            # the user holds its PAIR button. Use every scanner route, not just
            # the selected advertisement, so a stronger proxy does not hide a
            # shade that is also reachable on the local adapter.
            discovered: dict[str, BluetoothServiceInfoBleak] = {}
            for info in async_discovered_service_info(self.hass, connectable=True):
                if not info.name or info.address in current_ids:
                    continue
                local = self._local_service_info(info, prefer_pairing=True)
                if local is None:
                    continue
                if not (
                    is_pairing_mode(local.manufacturer_data)
                    or is_pairing_mode(info.manufacturer_data)
                ):
                    continue
                discovered[info.address] = local
            self._discovered_devices = discovered

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: info.name
                            for address, info in self._discovered_devices.items()
                        }
                    ),
                }
            ),
            errors=errors,
        )

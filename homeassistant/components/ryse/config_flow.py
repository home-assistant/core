"""Config flow for RYSE BLE integration."""

import logging
from typing import Any, override

from bleak import BleakError
import probatio
from ryseble import is_pairing_mode
from ryseble.device import RyseBLEDevice

from homeassistant.components.bluetooth import (
    BluetoothScannerDevice,
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import _async_unpair
from .const import DOMAIN, MANUFACTURER_ID, SERVICE_UUID
from .helpers import async_local_scanner_devices

_LOGGER = logging.getLogger(__name__)


def _is_ryse_advertisement(info: BluetoothServiceInfoBleak) -> bool:
    """Return True if *info* matches a RYSE shade."""
    return (
        MANUFACTURER_ID in info.manufacturer_data or SERVICE_UUID in info.service_uuids
    )


def _local_pairing_device(
    hass: HomeAssistant, address: str
) -> BluetoothScannerDevice | None:
    """Return a local-adapter sighting that is in pairing mode.

    Scanner advertisements are the source of truth. The Bluetooth manager's
    selected route can be a proxy, and a proxy PAIR flag cannot be bonded with
    the host BlueZ agent.
    """
    for scanner_device in async_local_scanner_devices(hass, address):
        if is_pairing_mode(scanner_device.advertisement.manufacturer_data):
            return scanner_device
    return None


def _scanner_device_name(scanner_device: BluetoothScannerDevice) -> str:
    """Return the name advertised to a local scanner."""
    advertisement = scanner_device.advertisement
    return advertisement.local_name or scanner_device.ble_device.name or ""


class RyseBLEDeviceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for RYSE BLE Device."""

    def __init__(self) -> None:
        """Initialize flow attributes."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def _async_pair(self, address: str) -> str | None:
        """Bond with the device via Bleak, then release the connection.

        Returns an error key, or None on success. Pairing is refused unless a
        local scanner advertisement still has the PAIR flag set; ryseble's
        BlueZ agent cannot pair through a Bluetooth proxy.
        """
        local = _local_pairing_device(self.hass, address)
        if local is None:
            if not async_local_scanner_devices(self.hass, address):
                return "not_local_source"
            return "not_in_pairing_mode"

        device = RyseBLEDevice(local.ble_device)
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
            # Teardown errors must not override a successful pair or chosen error key.
            await _async_unpair(device)
        return "cannot_connect"

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        # Keep match history and show the confirm step for proxy-only and idle
        # shades. Aborting never offers Ignore, and a background watcher would
        # have to outlive this flow. Pairing mode and a local adapter are
        # checked again on submit.
        self._discovery_info = discovery_info
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
            if error := await self._async_pair(discovery_info.address):
                errors["base"] = error
            else:
                return self.async_create_entry(title=name, data={})

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
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            if error := await self._async_pair(address):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=self._discovered_devices[address], data={}
                )

        if user_input is None:
            current_ids = self._async_current_ids(include_ignore=False)
            discovered: dict[str, str] = {}
            for info in async_discovered_service_info(self.hass, connectable=True):
                if info.address in current_ids or not _is_ryse_advertisement(info):
                    continue
                local = _local_pairing_device(self.hass, info.address)
                if local is None:
                    continue
                if name := _scanner_device_name(local) or info.name:
                    discovered[info.address] = name
            self._discovered_devices = discovered

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            address: f"{name} ({address})"
                            for address, name in self._discovered_devices.items()
                        }
                    ),
                }
            ),
            errors=errors,
        )

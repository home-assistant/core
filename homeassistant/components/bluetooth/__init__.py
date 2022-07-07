"""The bluetooth integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import dataclasses
from enum import Enum
import logging
from typing import Any

from bleak import BleakError
from bleak.backends.device import MANUFACTURERS, BLEDevice
from bleak.backends.scanner import AdvertisementData

# from homeassistant.components import websocket_api
# from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.data_entry_flow import BaseServiceInfo

# from homeassistant.helpers import discovery_flow, system_info
# from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .const import DOMAIN
from .models import HaBleakScanner
from .usage import install_multiple_bleak_catcher

# import voluptuous as vol

# from homeassistant.loader import async_get_bluetooth


_LOGGER = logging.getLogger(__name__)


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


SCANNING_MODE_TO_BLEAK = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}


@dataclasses.dataclass
class BluetoothServiceInfo(BaseServiceInfo):
    """Prepared info from bluetooth entries."""

    name: str
    address: str
    rssi: int
    manufacturer_data: dict[int, str]
    service_data: dict[str, bytes]
    service_uuids: list[str]

    @classmethod
    def from_advertisement(
        cls, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> BluetoothServiceInfo:
        """Create a BluetoothServiceInfo from an advertisement."""
        return cls(
            name=advertisement_data.local_name or device.name or device.address,
            address=device.address,
            rssi=device.rssi,
            manufacturer_data=advertisement_data.manufacturer_data,
            service_data=advertisement_data.service_data,
            service_uuids=advertisement_data.service_uuids,
        )

    @property
    def manufacturer(self) -> str | None:
        """Convert manufacturer data to a string."""
        for manufacturer in self.manufacturer_data:
            if name := MANUFACTURERS.get(manufacturer):
                return name
        return None


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfo, BluetoothChange], Awaitable]


@bind_hass
async def async_register_callback(
    hass: HomeAssistant,
    callback: BluetoothCallback,
    match_dict: None | dict[str, str] = None,
) -> Callable[[], None]:
    """Register to receive a callback on bluetooth change.

    Returns a callback that can be used to cancel the registration.
    """
    manager: BluetoothManager = hass.data[DOMAIN]
    return await manager.async_register_callback(callback, match_dict)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the bluetooth integration."""
    # bt = await async_get_bluetooth(hass)
    bluetooth: list[dict[str, str]] = []
    bluetooth_discovery = BluetoothManager(
        hass, bluetooth, BluetoothScanningMode.PASSIVE
    )
    await bluetooth_discovery.async_setup()
    hass.data[DOMAIN] = bluetooth

    # websocket_api.async_register_command(hass, list_devices)
    # websocket_api.async_register_command(hass, set_devices)

    return True


class BluetoothManager:
    """Manage Bluetooth."""

    def __init__(
        self,
        hass: HomeAssistant,
        bluetooth: list[dict[str, str]],
        scanning_mode: BluetoothScanningMode,
    ) -> None:
        """Init bluetooth discovery."""
        self.hass = hass
        self.scanning_mode = scanning_mode
        self.bluetooth = bluetooth
        self.scanner: HaBleakScanner | None = None
        self._cancel_device_detected: CALLBACK_TYPE | None = None
        self._scan_task: asyncio.Task | None = None
        self._callbacks: list[tuple[BluetoothCallback, dict[str, str]]] = []

    async def async_setup(self) -> None:
        """Set up BT Discovery."""
        try:
            self.scanner = HaBleakScanner(
                scanning_mode=SCANNING_MODE_TO_BLEAK[self.scanning_mode]
            )
        except BleakError as ex:
            _LOGGER.warning(
                "Could not create bluetooth scanner (is bluetooth present and enabled?): %s",
                ex,
            )
            return
        install_multiple_bleak_catcher(self.scanner)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.async_start)

    async def _async_start_scanner(self) -> None:
        """Start scanner and wait until canceled."""
        future: asyncio.Future[bool] = asyncio.Future()
        assert self.scanner is not None
        await self.scanner.start()
        await future

    @hass_callback
    def async_start(self, event: Event) -> None:
        """Start BT Discovery and run a manual scan."""
        _LOGGER.debug("Starting bluetooth scanner")
        assert self.scanner is not None
        self.scanner.register_detection_callback(self.scanner.async_callback_disptacher)
        self._cancel_device_detected = self.scanner.async_register_callback(
            self._device_detected
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        self._scan_task = self.hass.async_create_task(self._async_start_scanner())

    @hass_callback
    def _device_detected(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Handle a detected device."""
        service_info = BluetoothServiceInfo.from_advertisement(
            device, advertisement_data
        )
        _LOGGER.debug(
            "Device detected: %s with manufacturer: %s",
            service_info,
            service_info.manufacturer,
        )

    async def async_register_callback(
        self, callback: BluetoothCallback, match_dict: None | dict[str, str] = None
    ) -> Callable[[], None]:
        """Register a callback."""
        # if match_dict is None:
        lower_match_dict: dict[str, Any] = {}

        callback_entry = (callback, lower_match_dict)
        self._callbacks.append(callback_entry)

        @hass_callback
        def _async_remove_callback() -> None:
            self._callbacks.remove(callback_entry)

        return _async_remove_callback

    async def async_stop(self, event: Event) -> None:
        """Stop bluetooth discovery."""
        if self._cancel_device_detected:
            self._cancel_device_detected()
            self._cancel_device_detected = None
        if self._scan_task:
            self._scan_task.cancel()
            self._scan_task = None
        if self.scanner:
            await self.scanner.stop()

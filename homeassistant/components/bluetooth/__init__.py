"""The bluetooth integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import dataclasses
from enum import Enum
import fnmatch
import logging
from typing import Any

from bleak import BleakError
from bleak.backends.device import MANUFACTURERS, BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import BluetoothMatcher, async_get_bluetooth

from . import models
from .const import DOMAIN
from .models import HaBleakScanner
from .usage import install_multiple_bleak_catcher

_LOGGER = logging.getLogger(__name__)


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


SCANNING_MODE_TO_BLEAK = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}

LOCAL_NAME = "local_name"
SERVICE_UUID = "service_uuid"
MANUFACTURER_ID = "manufacturer_id"
MANUFACTURER_DATA_FIRST_BYTE = "manufacturer_data_first_byte"


@dataclasses.dataclass
class BluetoothServiceInfo(BaseServiceInfo):
    """Prepared info from bluetooth entries."""

    name: str
    address: str
    rssi: int
    manufacturer_data: dict[int, bytes]
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
            if manufacturer in MANUFACTURERS:
                name: str = MANUFACTURERS[manufacturer]
                return name
        return None

    @property
    def manufacturer_id(self) -> int | None:
        """Get the first manufacturer id."""
        for manufacturer in self.manufacturer_data:
            return manufacturer
        return None


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfo, BluetoothChange], Awaitable]


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
    integration_matchers = await async_get_bluetooth(hass)
    bluetooth: list[dict[str, str]] = []
    bluetooth_discovery = BluetoothManager(
        hass, integration_matchers, BluetoothScanningMode.PASSIVE
    )
    await bluetooth_discovery.async_setup()
    hass.data[DOMAIN] = bluetooth
    return True


class BluetoothManager:
    """Manage Bluetooth."""

    def __init__(
        self,
        hass: HomeAssistant,
        integration_matchers: list[BluetoothMatcher],
        scanning_mode: BluetoothScanningMode,
    ) -> None:
        """Init bluetooth discovery."""
        self.hass = hass
        self.scanning_mode = scanning_mode
        self._integration_matchers = integration_matchers
        self.scanner: HaBleakScanner | None = None
        self._cancel_device_detected: CALLBACK_TYPE | None = None
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

    async def async_start(self, event: Event) -> None:
        """Start BT Discovery and run a manual scan."""
        _LOGGER.debug("Starting bluetooth scanner")
        assert self.scanner is not None
        self.scanner.register_detection_callback(self.scanner.async_callback_disptacher)
        self._cancel_device_detected = self.scanner.async_register_callback(
            self._device_detected, {}
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        await self.scanner.start()

    @hass_callback
    def _device_detected(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Handle a detected device."""
        name = advertisement_data.local_name or device.name or device.address
        _LOGGER.debug(
            "Device detected: %s with advertisement_data: %s",
            device,
            advertisement_data,
        )
        matched_domains = set()
        for matcher in self._integration_matchers:
            domain = matcher["domain"]
            if (
                matcher_local_name := matcher.get(LOCAL_NAME)
            ) is not None and not fnmatch.fnmatch(name, matcher_local_name):
                continue

            if (
                (matcher_service_uuid := matcher.get(SERVICE_UUID)) is not None
                and matcher_service_uuid not in advertisement_data.service_uuids
            ):
                continue

            if (
                (matcher_manfacturer_id := matcher.get(MANUFACTURER_ID)) is not None
                and matcher_manfacturer_id not in advertisement_data.manufacturer_data
            ):
                continue

            if (
                matcher_manufacturer_data_first_byte := matcher.get(
                    MANUFACTURER_DATA_FIRST_BYTE
                )
            ) is not None and not any(
                matcher_manufacturer_data_first_byte == manufacturer_data[0]
                for manufacturer_data in advertisement_data.manufacturer_data.values()
            ):
                continue

            _LOGGER.debug("Matched %s against %s", advertisement_data, matcher)
            matched_domains.add(domain)

        if not matched_domains:
            return

        service_info = BluetoothServiceInfo.from_advertisement(
            device, advertisement_data
        )
        for domain in matched_domains:
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_BLUETOOTH},
                service_info,
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
        if self.scanner:
            await self.scanner.stop()
        models.HA_BLEAK_SCANNER = None

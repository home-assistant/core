"""The bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from enum import Enum
import fnmatch
from functools import cached_property
import logging
import platform
from typing import Final

from bleak import BleakError
from bleak.backends.device import MANUFACTURERS, BLEDevice
from bleak.backends.scanner import AdvertisementData
from lru import LRU  # pylint: disable=no-name-in-module

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
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

MAX_REMEMBER_ADDRESSES: Final = 2048


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


SCANNING_MODE_TO_BLEAK = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}

LOCAL_NAME: Final = "local_name"
SERVICE_UUID: Final = "service_uuid"
MANUFACTURER_ID: Final = "manufacturer_id"
MANUFACTURER_DATA_FIRST_BYTE: Final = "manufacturer_data_first_byte"


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

    @cached_property
    def manufacturer(self) -> str | None:
        """Convert manufacturer data to a string."""
        for manufacturer in self.manufacturer_data:
            if manufacturer in MANUFACTURERS:
                name: str = MANUFACTURERS[manufacturer]
                return name
        return None

    @cached_property
    def manufacturer_id(self) -> int | None:
        """Get the first manufacturer id."""
        for manufacturer in self.manufacturer_data:
            return manufacturer
        return None


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfo, BluetoothChange], None]


@hass_callback
def async_register_callback(
    hass: HomeAssistant,
    callback: BluetoothCallback,
    match_dict: BluetoothMatcher | None,
) -> Callable[[], None]:
    """Register to receive a callback on bluetooth change.

    Returns a callback that can be used to cancel the registration.
    """
    manager: BluetoothManager = hass.data[DOMAIN]
    return manager.async_register_callback(callback, match_dict)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the bluetooth integration."""
    integration_matchers = await async_get_bluetooth(hass)
    bluetooth_discovery = BluetoothManager(
        hass, integration_matchers, BluetoothScanningMode.PASSIVE
    )
    await bluetooth_discovery.async_setup()
    hass.data[DOMAIN] = bluetooth_discovery
    return True


def _ble_device_matches(
    matcher: BluetoothMatcher, device: BLEDevice, advertisement_data: AdvertisementData
) -> bool:
    """Check if a ble device and advertisement_data matches the matcher."""
    if (
        matcher_local_name := matcher.get(LOCAL_NAME)
    ) is not None and not fnmatch.fnmatch(
        advertisement_data.local_name or device.name or device.address,
        matcher_local_name,
    ):
        return False

    if (
        matcher_service_uuid := matcher.get(SERVICE_UUID)
    ) is not None and matcher_service_uuid not in advertisement_data.service_uuids:
        return False

    if (
        (matcher_manfacturer_id := matcher.get(MANUFACTURER_ID)) is not None
        and matcher_manfacturer_id not in advertisement_data.manufacturer_data
    ):
        return False

    if (
        matcher_manufacturer_data_first_byte := matcher.get(
            MANUFACTURER_DATA_FIRST_BYTE
        )
    ) is not None and not any(
        matcher_manufacturer_data_first_byte == manufacturer_data[0]
        for manufacturer_data in advertisement_data.manufacturer_data.values()
    ):
        return False

    return True


@hass_callback
def async_enable_rssi_updates() -> None:
    """Bleak filters out RSSI updates by default on linux only."""
    # We want RSSI updates
    if platform.system() == "Linux":
        from bleak.backends.bluezdbus import (  # pylint: disable=import-outside-toplevel
            scanner,
        )

        scanner._ADVERTISING_DATA_PROPERTIES.add(  # pylint: disable=protected-access
            "RSSI"
        )


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
        self._callbacks: list[tuple[BluetoothCallback, BluetoothMatcher | None]] = []
        # Some devices use a random address so we need to use
        # an LRU to avoid memory issues.
        self._matched: LRU = LRU(MAX_REMEMBER_ADDRESSES)

    async def async_setup(self) -> None:
        """Set up BT Discovery."""
        try:
            self.scanner = HaBleakScanner(
                scanning_mode=SCANNING_MODE_TO_BLEAK[self.scanning_mode]
            )
        except (FileNotFoundError, BleakError) as ex:
            _LOGGER.warning(
                "Could not create bluetooth scanner (is bluetooth present and enabled?): %s",
                ex,
            )
            return
        async_enable_rssi_updates()
        install_multiple_bleak_catcher(self.scanner)
        # We have to start it right away as some integrations might
        # need it straight away.
        _LOGGER.debug("Starting bluetooth scanner")
        self.scanner.register_detection_callback(self.scanner.async_callback_dispatcher)
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
        matched_domains: set[str] | None = None
        if device.address not in self._matched:
            matched_domains = {
                matcher["domain"]
                for matcher in self._integration_matchers
                if _ble_device_matches(matcher, device, advertisement_data)
            }
            if matched_domains:
                self._matched[device.address] = True
            _LOGGER.debug(
                "Device detected: %s with advertisement_data: %s matched domains: %s",
                device,
                advertisement_data,
                matched_domains,
            )

        if not matched_domains and not self._callbacks:
            return

        service_info: BluetoothServiceInfo | None = None
        for callback, matcher in self._callbacks:
            if matcher is None or _ble_device_matches(
                matcher, device, advertisement_data
            ):
                if service_info is None:
                    service_info = BluetoothServiceInfo.from_advertisement(
                        device, advertisement_data
                    )
                try:
                    callback(service_info, BluetoothChange.ADVERTISEMENT)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error in bluetooth callback")

        if not matched_domains:
            return
        if service_info is None:
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

    @hass_callback
    def async_register_callback(
        self, callback: BluetoothCallback, match_dict: BluetoothMatcher | None = None
    ) -> Callable[[], None]:
        """Register a callback."""
        callback_entry = (callback, match_dict)
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

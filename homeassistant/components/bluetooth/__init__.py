"""The bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import fnmatch
import logging
from typing import Final, TypedDict

from bleak import BleakError
from bleak.backends.device import BLEDevice
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
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import (
    BluetoothMatcher,
    BluetoothMatcherOptional,
    async_get_bluetooth,
)

from . import models
from .const import DOMAIN
from .models import HaBleakScanner
from .usage import install_multiple_bleak_catcher

_LOGGER = logging.getLogger(__name__)

MAX_REMEMBER_ADDRESSES: Final = 2048

SLEEP_RECOVERY_INTERVAL: Final = 120

SOURCE_LOCAL: Final = "local"


@dataclass
class BluetoothServiceInfoBleak(BluetoothServiceInfo):  # type: ignore[misc]
    """BluetoothServiceInfo with bleak data.

    Integrations may need BLEDevice and AdvertisementData
    to connect to the device without having bleak trigger
    another scan to translate the address to the system's
    internal details.
    """

    device: BLEDevice
    advertisement: AdvertisementData

    @classmethod
    def from_advertisement(
        cls, device: BLEDevice, advertisement_data: AdvertisementData, source: str
    ) -> BluetoothServiceInfo:
        """Create a BluetoothServiceInfoBleak from an advertisement."""
        return cls(
            name=advertisement_data.local_name or device.name or device.address,
            address=device.address,
            rssi=device.rssi,
            manufacturer_data=advertisement_data.manufacturer_data,
            service_data=advertisement_data.service_data,
            service_uuids=advertisement_data.service_uuids,
            source=source,
            device=device,
            advertisement=advertisement_data,
        )


class BluetoothCallbackMatcherOptional(TypedDict, total=False):
    """Matcher for the bluetooth integration for callback optional fields."""

    address: str


class BluetoothCallbackMatcher(
    BluetoothMatcherOptional,
    BluetoothCallbackMatcherOptional,
):
    """Callback matcher for the bluetooth integration."""


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


SCANNING_MODE_TO_BLEAK = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}

ADDRESS: Final = "address"
LOCAL_NAME: Final = "local_name"
SERVICE_UUID: Final = "service_uuid"
MANUFACTURER_ID: Final = "manufacturer_id"
MANUFACTURER_DATA_START: Final = "manufacturer_data_start"


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]


@hass_callback
def async_discovered_service_info(
    hass: HomeAssistant,
) -> list[BluetoothServiceInfoBleak]:
    """Return the discovered devices list."""
    if DOMAIN not in hass.data:
        return []
    manager: BluetoothManager = hass.data[DOMAIN]
    return manager.async_discovered_service_info()


@hass_callback
def async_ble_device_from_address(
    hass: HomeAssistant,
    address: str,
) -> BLEDevice | None:
    """Return BLEDevice for an address if its present."""
    if DOMAIN not in hass.data:
        return None
    manager: BluetoothManager = hass.data[DOMAIN]
    return manager.async_ble_device_from_address(address)


@hass_callback
def async_address_present(
    hass: HomeAssistant,
    address: str,
) -> bool:
    """Check if an address is present in the bluetooth device list."""
    if DOMAIN not in hass.data:
        return False
    manager: BluetoothManager = hass.data[DOMAIN]
    return manager.async_address_present(address)


@hass_callback
def async_register_callback(
    hass: HomeAssistant,
    callback: BluetoothCallback,
    match_dict: BluetoothCallbackMatcher | None,
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
    matcher: BluetoothCallbackMatcher | BluetoothMatcher,
    device: BLEDevice,
    advertisement_data: AdvertisementData,
) -> bool:
    """Check if a ble device and advertisement_data matches the matcher."""
    if (
        matcher_address := matcher.get(ADDRESS)
    ) is not None and device.address != matcher_address:
        return False

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
        matcher_manufacturer_data_start := matcher.get(MANUFACTURER_DATA_START)
    ) is not None:
        matcher_manufacturer_data_start_bytes = bytearray(
            matcher_manufacturer_data_start
        )
        if not any(
            manufacturer_data.startswith(matcher_manufacturer_data_start_bytes)
            for manufacturer_data in advertisement_data.manufacturer_data.values()
        ):
            return False

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
        self._cancel_sleep_recovery: CALLBACK_TYPE | None = None
        self._callbacks: list[
            tuple[BluetoothCallback, BluetoothCallbackMatcher | None]
        ] = []
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
        install_multiple_bleak_catcher(self.scanner)
        self.async_setup_sleep_recovery()
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
    def async_setup_sleep_recovery(self) -> None:
        """Set up the sleep recovery."""

        async def async_sleep_recovery(now: datetime) -> None:
            """Restart bluetooth discovery on sleep."""
            _LOGGER.warning(
                "Restarting bluetooth scanner? -- is_scanning: %s",
                getattr(self.scanner, "is_scanning", None),
            )
            assert self.scanner is not None
            ## TODO: scanner has is_scanning property for mac but not linux so
            ## on linux we need to restart if nothing seen in last 2 minutes
            _LOGGER.warning("Discovered devices: %s", self.scanner.discovered_devices)

        self._cancel_sleep_recovery = async_track_time_interval(
            self.hass, async_sleep_recovery, timedelta(seconds=SLEEP_RECOVERY_INTERVAL)
        )

    @hass_callback
    def _device_detected(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Handle a detected device."""
        matched_domains: set[str] | None = None
        match_key = (device.address, bool(advertisement_data.manufacturer_data))
        match_key_has_mfr_data = (device.address, True)

        # If we matched without manufacturer_data, we need to do it again
        # since we may think the device is unsupported otherwise
        if (
            match_key_has_mfr_data not in self._matched
            and match_key not in self._matched
        ):
            matched_domains = {
                matcher["domain"]
                for matcher in self._integration_matchers
                if _ble_device_matches(matcher, device, advertisement_data)
            }
            if matched_domains:
                self._matched[match_key] = True
            _LOGGER.debug(
                "Device detected: %s with advertisement_data: %s matched domains: %s",
                device,
                advertisement_data,
                matched_domains,
            )

        if not matched_domains and not self._callbacks:
            return

        service_info: BluetoothServiceInfoBleak | None = None
        for callback, matcher in self._callbacks:
            if matcher is None or _ble_device_matches(
                matcher, device, advertisement_data
            ):
                if service_info is None:
                    service_info = BluetoothServiceInfoBleak.from_advertisement(
                        device, advertisement_data, SOURCE_LOCAL
                    )
                try:
                    callback(service_info, BluetoothChange.ADVERTISEMENT)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error in bluetooth callback")

        if not matched_domains:
            return
        if service_info is None:
            service_info = BluetoothServiceInfoBleak.from_advertisement(
                device, advertisement_data, SOURCE_LOCAL
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
        self,
        callback: BluetoothCallback,
        matcher: BluetoothCallbackMatcher | None = None,
    ) -> Callable[[], None]:
        """Register a callback."""
        callback_entry = (callback, matcher)
        self._callbacks.append(callback_entry)

        @hass_callback
        def _async_remove_callback() -> None:
            self._callbacks.remove(callback_entry)

        # If we have history for the subscriber, we can trigger the callback
        # immediately with the last packet so the subscriber can see the
        # device.
        if (
            matcher
            and (address := matcher.get(ADDRESS))
            and models.HA_BLEAK_SCANNER
            and (device_adv_data := models.HA_BLEAK_SCANNER.history.get(address))
        ):
            try:
                callback(
                    BluetoothServiceInfoBleak.from_advertisement(
                        *device_adv_data, SOURCE_LOCAL
                    ),
                    BluetoothChange.ADVERTISEMENT,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error in bluetooth callback")

        return _async_remove_callback

    @hass_callback
    def async_ble_device_from_address(self, address: str) -> BLEDevice | None:
        """Return the BLEDevice if present."""
        if models.HA_BLEAK_SCANNER and (
            ble_adv := models.HA_BLEAK_SCANNER.history.get(address)
        ):
            return ble_adv[0]
        return None

    @hass_callback
    def async_address_present(self, address: str) -> bool:
        """Return if the address is present."""
        return bool(
            models.HA_BLEAK_SCANNER
            and any(
                device.address == address
                for device in models.HA_BLEAK_SCANNER.discovered_devices
            )
        )

    @hass_callback
    def async_discovered_service_info(self) -> list[BluetoothServiceInfo]:
        """Return if the address is present."""
        if models.HA_BLEAK_SCANNER:
            discovered = models.HA_BLEAK_SCANNER.discovered_devices
            history = models.HA_BLEAK_SCANNER.history
            return [
                BluetoothServiceInfoBleak.from_advertisement(
                    *history[device.address], SOURCE_LOCAL
                )
                for device in discovered
                if device.address in history
            ]
        return []

    async def async_stop(self, event: Event) -> None:
        """Stop bluetooth discovery."""
        if self._cancel_device_detected:
            self._cancel_device_detected()
            self._cancel_device_detected = None
        if self._cancel_sleep_recovery:
            self._cancel_sleep_recovery()
            self._cancel_sleep_recovery = None
        if self.scanner:
            await self.scanner.stop()
        models.HA_BLEAK_SCANNER = None

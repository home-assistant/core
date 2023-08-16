"""The bluetooth integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
import platform
from typing import Any

import bleak
from bleak import BleakError
from bleak.assigned_numbers import AdvertisementDataType
from bleak.backends.bluezdbus.advertisement_monitor import OrPattern
from bleak.backends.bluezdbus.scanner import BlueZScannerArgs
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData, AdvertisementDataCallback
from bleak_retry_connector import restore_discoveries
from bluetooth_adapters import DEFAULT_ADDRESS
from dbus_fast import InvalidMessageError

from homeassistant.core import HomeAssistant, callback as hass_callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.package import is_docker_env

from .base_scanner import MONOTONIC_TIME, BaseHaScanner
from .const import (
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
    SOURCE_LOCAL,
    START_TIMEOUT,
)
from .models import BluetoothScanningMode, BluetoothServiceInfoBleak
from .util import async_reset_adapter

OriginalBleakScanner = bleak.BleakScanner

# or_patterns is a workaround for the fact that passive scanning
# needs at least one matcher to be set. The below matcher
# will match all devices.
PASSIVE_SCANNER_ARGS = BlueZScannerArgs(
    or_patterns=[
        OrPattern(0, AdvertisementDataType.FLAGS, b"\x06"),
        OrPattern(0, AdvertisementDataType.FLAGS, b"\x1a"),
    ]
)
_LOGGER = logging.getLogger(__name__)


# If the adapter is in a stuck state the following errors are raised:
NEED_RESET_ERRORS = [
    "org.bluez.Error.Failed",
    "org.bluez.Error.InProgress",
    "org.bluez.Error.NotReady",
    "not found",
]

# When the adapter is still initializing, the scanner will raise an exception
# with org.freedesktop.DBus.Error.UnknownObject
WAIT_FOR_ADAPTER_TO_INIT_ERRORS = ["org.freedesktop.DBus.Error.UnknownObject"]
ADAPTER_INIT_TIME = 1.5

START_ATTEMPTS = 3

SCANNING_MODE_TO_BLEAK = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}

# The minimum number of seconds to know
# the adapter has not had advertisements
# and we already tried to restart the scanner
# without success when the first time the watch
# dog hit the failure path.
SCANNER_WATCHDOG_MULTIPLE = (
    SCANNER_WATCHDOG_TIMEOUT + SCANNER_WATCHDOG_INTERVAL.total_seconds()
)


class ScannerStartError(HomeAssistantError):
    """Error to indicate that the scanner failed to start."""


def create_bleak_scanner(
    detection_callback: AdvertisementDataCallback,
    scanning_mode: BluetoothScanningMode,
    adapter: str | None,
) -> bleak.BleakScanner:
    """Create a Bleak scanner."""
    scanner_kwargs: dict[str, Any] = {
        "detection_callback": detection_callback,
        "scanning_mode": SCANNING_MODE_TO_BLEAK[scanning_mode],
    }
    system = platform.system()
    if system == "Linux":
        # Only Linux supports multiple adapters
        if adapter:
            scanner_kwargs["adapter"] = adapter
        if scanning_mode == BluetoothScanningMode.PASSIVE:
            scanner_kwargs["bluez"] = PASSIVE_SCANNER_ARGS
    elif system == "Darwin":
        # We want mac address on macOS
        scanner_kwargs["cb"] = {"use_bdaddr": True}
    _LOGGER.debug("Initializing bluetooth scanner with %s", scanner_kwargs)

    try:
        return OriginalBleakScanner(**scanner_kwargs)
    except (FileNotFoundError, BleakError) as ex:
        raise RuntimeError(f"Failed to initialize Bluetooth: {ex}") from ex


class HaScanner(BaseHaScanner):
    """Operate and automatically recover a BleakScanner.

    Multiple BleakScanner can be used at the same time
    if there are multiple adapters. This is only useful
    if the adapters are not located physically next to each other.

    Example use cases are usbip, a long extension cable, usb to bluetooth
    over ethernet, usb over ethernet, etc.
    """

    scanner: bleak.BleakScanner

    def __init__(
        self,
        hass: HomeAssistant,
        mode: BluetoothScanningMode,
        adapter: str,
        address: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
    ) -> None:
        """Init bluetooth discovery."""
        self.mac_address = address
        source = address if address != DEFAULT_ADDRESS else adapter or SOURCE_LOCAL
        super().__init__(hass, source, adapter)
        self.connectable = True
        self.mode = mode
        self._start_stop_lock = asyncio.Lock()
        self._new_info_callback = new_info_callback
        self.scanning = False

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        return self.scanner.discovered_devices

    @property
    def discovered_devices_and_advertisement_data(
        self,
    ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
        """Return a list of discovered devices and advertisement data."""
        return self.scanner.discovered_devices_and_advertisement_data

    @hass_callback
    def async_setup(self) -> None:
        """Set up the scanner."""
        self.scanner = create_bleak_scanner(
            self._async_detection_callback, self.mode, self.adapter
        )

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        base_diag = await super().async_diagnostics()
        return base_diag | {
            "adapter": self.adapter,
        }

    @hass_callback
    def _async_detection_callback(
        self,
        device: BLEDevice,
        advertisement_data: AdvertisementData,
    ) -> None:
        """Call the callback when an advertisement is received.

        Currently this is used to feed the callbacks into the
        central manager.
        """
        callback_time = MONOTONIC_TIME()
        if (
            advertisement_data.local_name
            or advertisement_data.manufacturer_data
            or advertisement_data.service_data
            or advertisement_data.service_uuids
        ):
            # Don't count empty advertisements
            # as the adapter is in a failure
            # state if all the data is empty.
            self._last_detection = callback_time
        self._new_info_callback(
            BluetoothServiceInfoBleak(
                name=advertisement_data.local_name or device.name or device.address,
                address=device.address,
                rssi=advertisement_data.rssi,
                manufacturer_data=advertisement_data.manufacturer_data,
                service_data=advertisement_data.service_data,
                service_uuids=advertisement_data.service_uuids,
                source=self.source,
                device=device,
                advertisement=advertisement_data,
                connectable=True,
                time=callback_time,
            )
        )

    async def async_start(self) -> None:
        """Start bluetooth scanner."""
        async with self._start_stop_lock:
            await self._async_start()

    async def _async_start(self) -> None:
        """Start bluetooth scanner under the lock."""
        for attempt in range(START_ATTEMPTS):
            _LOGGER.debug(
                "%s: Starting bluetooth discovery attempt: (%s/%s)",
                self.name,
                attempt + 1,
                START_ATTEMPTS,
            )
            try:
                async with asyncio.timeout(START_TIMEOUT):
                    await self.scanner.start()  # type: ignore[no-untyped-call]
            except InvalidMessageError as ex:
                _LOGGER.debug(
                    "%s: Invalid DBus message received: %s",
                    self.name,
                    ex,
                    exc_info=True,
                )
                raise ScannerStartError(
                    f"{self.name}: Invalid DBus message received: {ex}; "
                    "try restarting `dbus`"
                ) from ex
            except BrokenPipeError as ex:
                _LOGGER.debug(
                    "%s: DBus connection broken: %s", self.name, ex, exc_info=True
                )
                if is_docker_env():
                    raise ScannerStartError(
                        f"{self.name}: DBus connection broken: {ex}; try restarting "
                        "`bluetooth`, `dbus`, and finally the docker container"
                    ) from ex
                raise ScannerStartError(
                    f"{self.name}: DBus connection broken: {ex}; try restarting "
                    "`bluetooth` and `dbus`"
                ) from ex
            except FileNotFoundError as ex:
                _LOGGER.debug(
                    "%s: FileNotFoundError while starting bluetooth: %s",
                    self.name,
                    ex,
                    exc_info=True,
                )
                if is_docker_env():
                    raise ScannerStartError(
                        f"{self.name}: DBus service not found; docker config may "
                        "be missing `-v /run/dbus:/run/dbus:ro`: {ex}"
                    ) from ex
                raise ScannerStartError(
                    f"{self.name}: DBus service not found; make sure the DBus socket "
                    f"is available to Home Assistant: {ex}"
                ) from ex
            except asyncio.TimeoutError as ex:
                if attempt == 0:
                    await self._async_reset_adapter()
                    continue
                raise ScannerStartError(
                    f"{self.name}: Timed out starting Bluetooth after"
                    f" {START_TIMEOUT} seconds"
                ) from ex
            except BleakError as ex:
                error_str = str(ex)
                if attempt == 0:
                    if any(
                        needs_reset_error in error_str
                        for needs_reset_error in NEED_RESET_ERRORS
                    ):
                        await self._async_reset_adapter()
                    continue
                if attempt != START_ATTEMPTS - 1:
                    # If we are not out of retry attempts, and the
                    # adapter is still initializing, wait a bit and try again.
                    if any(
                        wait_error in error_str
                        for wait_error in WAIT_FOR_ADAPTER_TO_INIT_ERRORS
                    ):
                        _LOGGER.debug(
                            "%s: Waiting for adapter to initialize; attempt (%s/%s)",
                            self.name,
                            attempt + 1,
                            START_ATTEMPTS,
                        )
                        await asyncio.sleep(ADAPTER_INIT_TIME)
                        continue

                _LOGGER.debug(
                    "%s: BleakError while starting bluetooth; attempt: (%s/%s): %s",
                    self.name,
                    attempt + 1,
                    START_ATTEMPTS,
                    ex,
                    exc_info=True,
                )
                raise ScannerStartError(
                    f"{self.name}: Failed to start Bluetooth: {ex}"
                ) from ex

            # Everything is fine, break out of the loop
            break

        self.scanning = True
        self._async_setup_scanner_watchdog()
        await restore_discoveries(self.scanner, self.adapter)

    @hass_callback
    def _async_scanner_watchdog(self, now: datetime) -> None:
        """Check if the scanner is running."""
        if not self._async_watchdog_triggered():
            return
        if self._start_stop_lock.locked():
            _LOGGER.debug(
                "%s: Scanner is already restarting, deferring restart",
                self.name,
            )
            return
        _LOGGER.info(
            "%s: Bluetooth scanner has gone quiet for %ss, restarting",
            self.name,
            SCANNER_WATCHDOG_TIMEOUT,
        )
        self.hass.async_create_task(self._async_restart_scanner())

    async def _async_restart_scanner(self) -> None:
        """Restart the scanner."""
        async with self._start_stop_lock:
            time_since_last_detection = MONOTONIC_TIME() - self._last_detection
            # Stop the scanner but not the watchdog
            # since we want to try again later if it's still quiet
            await self._async_stop_scanner()
            # If there have not been any valid advertisements,
            # or the watchdog has hit the failure path multiple times,
            # do the reset.
            if (
                self._start_time == self._last_detection
                or time_since_last_detection > SCANNER_WATCHDOG_MULTIPLE
            ):
                await self._async_reset_adapter()
            try:
                await self._async_start()
            except ScannerStartError as ex:
                _LOGGER.error(
                    "%s: Failed to restart Bluetooth scanner: %s",
                    self.name,
                    ex,
                    exc_info=True,
                )

    async def _async_reset_adapter(self) -> None:
        """Reset the adapter."""
        # There is currently nothing the user can do to fix this
        # so we log at debug level. If we later come up with a repair
        # strategy, we will change this to raise a repair issue as well.
        _LOGGER.debug("%s: adapter stopped responding; executing reset", self.name)
        result = await async_reset_adapter(self.adapter, self.mac_address)
        _LOGGER.debug("%s: adapter reset result: %s", self.name, result)

    async def async_stop(self) -> None:
        """Stop bluetooth scanner."""
        async with self._start_stop_lock:
            self._async_stop_scanner_watchdog()
            await self._async_stop_scanner()

    async def _async_stop_scanner(self) -> None:
        """Stop bluetooth discovery under the lock."""
        self.scanning = False
        _LOGGER.debug("%s: Stopping bluetooth discovery", self.name)
        try:
            await self.scanner.stop()  # type: ignore[no-untyped-call]
        except BleakError as ex:
            # This is not fatal, and they may want to reload
            # the config entry to restart the scanner if they
            # change the bluetooth dongle.
            _LOGGER.error("%s: Error stopping scanner: %s", self.name, ex)

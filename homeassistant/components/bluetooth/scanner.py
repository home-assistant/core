"""The bluetooth integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
import platform
import time

import async_timeout
import bleak
from bleak import BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from dbus_next import InvalidMessageError

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.package import is_docker_env

from .const import (
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
    SOURCE_LOCAL,
    START_TIMEOUT,
)
from .models import BluetoothScanningMode
from .util import adapter_human_name, async_reset_adapter

OriginalBleakScanner = bleak.BleakScanner
MONOTONIC_TIME = time.monotonic


_LOGGER = logging.getLogger(__name__)


MONOTONIC_TIME = time.monotonic

NEED_RESET_ERRORS = [
    "org.bluez.Error.Failed",
    "org.bluez.Error.InProgress",
    "org.bluez.Error.NotReady",
]
START_ATTEMPTS = 2

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
    scanning_mode: BluetoothScanningMode, adapter: str | None
) -> bleak.BleakScanner:
    """Create a Bleak scanner."""
    scanner_kwargs = {"scanning_mode": SCANNING_MODE_TO_BLEAK[scanning_mode]}
    # Only Linux supports multiple adapters
    if adapter and platform.system() == "Linux":
        scanner_kwargs["adapter"] = adapter
    _LOGGER.debug("Initializing bluetooth scanner with %s", scanner_kwargs)
    try:
        return OriginalBleakScanner(**scanner_kwargs)  # type: ignore[arg-type]
    except (FileNotFoundError, BleakError) as ex:
        raise RuntimeError(f"Failed to initialize Bluetooth: {ex}") from ex


class HaScanner:
    """Operate and automatically recover a BleakScanner.

    Multiple BleakScanner can be used at the same time
    if there are multiple adapters. This is only useful
    if the adapters are not located physically next to each other.

    Example use cases are usbip, a long extension cable, usb to bluetooth
    over ethernet, usb over ethernet, etc.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        scanner: bleak.BleakScanner,
        adapter: str,
        address: str,
    ) -> None:
        """Init bluetooth discovery."""
        self.hass = hass
        self.scanner = scanner
        self.adapter = adapter
        self._start_stop_lock = asyncio.Lock()
        self._cancel_stop: CALLBACK_TYPE | None = None
        self._cancel_watchdog: CALLBACK_TYPE | None = None
        self._last_detection = 0.0
        self._start_time = 0.0
        self._callbacks: list[
            Callable[[BLEDevice, AdvertisementData, float, str], None]
        ] = []
        self.name = adapter_human_name(adapter, address)
        self.source = self.adapter or SOURCE_LOCAL

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        return self.scanner.discovered_devices

    @hass_callback
    def async_register_callback(
        self, callback: Callable[[BLEDevice, AdvertisementData, float, str], None]
    ) -> CALLBACK_TYPE:
        """Register a callback.

        Currently this is used to feed the callbacks into the
        central manager.
        """

        def _remove() -> None:
            self._callbacks.remove(callback)

        self._callbacks.append(callback)
        return _remove

    @hass_callback
    def _async_detection_callback(
        self,
        ble_device: BLEDevice,
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
        for callback in self._callbacks:
            callback(ble_device, advertisement_data, callback_time, self.source)

    async def async_start(self) -> None:
        """Start bluetooth scanner."""
        self.scanner.register_detection_callback(self._async_detection_callback)

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
                async with async_timeout.timeout(START_TIMEOUT):
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
                    f"{self.name}: Timed out starting Bluetooth after {START_TIMEOUT} seconds"
                ) from ex
            except BleakError as ex:
                if attempt == 0:
                    error_str = str(ex)
                    if any(
                        needs_reset_error in error_str
                        for needs_reset_error in NEED_RESET_ERRORS
                    ):
                        await self._async_reset_adapter()
                    continue
                _LOGGER.debug(
                    "%s: BleakError while starting bluetooth: %s",
                    self.name,
                    ex,
                    exc_info=True,
                )
                raise ScannerStartError(
                    f"{self.name}: Failed to start Bluetooth: {ex}"
                ) from ex

            # Everything is fine, break out of the loop
            break

        self._async_setup_scanner_watchdog()
        self._cancel_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_hass_stopping
        )

    @hass_callback
    def _async_setup_scanner_watchdog(self) -> None:
        """If Dbus gets restarted or updated, we need to restart the scanner."""
        self._start_time = self._last_detection = MONOTONIC_TIME()
        if not self._cancel_watchdog:
            self._cancel_watchdog = async_track_time_interval(
                self.hass, self._async_scanner_watchdog, SCANNER_WATCHDOG_INTERVAL
            )

    async def _async_scanner_watchdog(self, now: datetime) -> None:
        """Check if the scanner is running."""
        time_since_last_detection = MONOTONIC_TIME() - self._last_detection
        _LOGGER.debug(
            "%s: Scanner watchdog time_since_last_detection: %s",
            self.name,
            time_since_last_detection,
        )
        if time_since_last_detection < SCANNER_WATCHDOG_TIMEOUT:
            return
        _LOGGER.info(
            "%s: Bluetooth scanner has gone quiet for %ss, restarting",
            self.name,
            SCANNER_WATCHDOG_TIMEOUT,
        )
        async with self._start_stop_lock:
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

    async def _async_hass_stopping(self, event: Event) -> None:
        """Stop the Bluetooth integration at shutdown."""
        self._cancel_stop = None
        await self.async_stop()

    async def _async_reset_adapter(self) -> None:
        """Reset the adapter."""
        _LOGGER.warning("%s: adapter stopped responding; executing reset", self.name)
        result = await async_reset_adapter(self.adapter)
        _LOGGER.info("%s: adapter reset result: %s", self.name, result)

    async def async_stop(self) -> None:
        """Stop bluetooth scanner."""
        async with self._start_stop_lock:
            await self._async_stop()

    async def _async_stop(self) -> None:
        """Cancel watchdog and bluetooth discovery under the lock."""
        if self._cancel_watchdog:
            self._cancel_watchdog()
            self._cancel_watchdog = None
        await self._async_stop_scanner()

    async def _async_stop_scanner(self) -> None:
        """Stop bluetooth discovery under the lock."""
        if self._cancel_stop:
            self._cancel_stop()
            self._cancel_stop = None
        _LOGGER.debug("%s: Stopping bluetooth discovery", self.name)
        try:
            await self.scanner.stop()  # type: ignore[no-untyped-call]
        except BleakError as ex:
            # This is not fatal, and they may want to reload
            # the config entry to restart the scanner if they
            # change the bluetooth dongle.
            _LOGGER.error("%s: Error stopping scanner: %s", self.name, ex)

"""The bluetooth integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING

import async_timeout
from bleak import BleakError
from dbus_next import InvalidMessageError

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.package import is_docker_env

from . import models
from .const import (
    DEFAULT_ADAPTERS,
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
    SOURCE_LOCAL,
    START_TIMEOUT,
    UNAVAILABLE_TRACK_SECONDS,
)
from .match import (
    ADDRESS,
    BluetoothCallbackMatcher,
    IntegrationMatcher,
    ble_device_matches,
)
from .models import (
    BluetoothCallback,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    HaBleakScanner,
    HaBleakScannerWrapper,
)
from .usage import install_multiple_bleak_catcher, uninstall_multiple_bleak_catcher

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData


_LOGGER = logging.getLogger(__name__)


MONOTONIC_TIME = time.monotonic


SCANNING_MODE_TO_BLEAK = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}


class BluetoothManager:
    """Manage Bluetooth."""

    def __init__(
        self,
        hass: HomeAssistant,
        integration_matcher: IntegrationMatcher,
    ) -> None:
        """Init bluetooth discovery."""
        self.hass = hass
        self._integration_matcher = integration_matcher
        self.scanner: HaBleakScanner | None = None
        self.start_stop_lock = asyncio.Lock()
        self._cancel_device_detected: CALLBACK_TYPE | None = None
        self._cancel_unavailable_tracking: CALLBACK_TYPE | None = None
        self._cancel_stop: CALLBACK_TYPE | None = None
        self._cancel_watchdog: CALLBACK_TYPE | None = None
        self._unavailable_callbacks: dict[str, list[Callable[[str], None]]] = {}
        self._callbacks: list[
            tuple[BluetoothCallback, BluetoothCallbackMatcher | None]
        ] = []
        self._last_detection = 0.0
        self._reloading = False
        self._adapter: str | None = None
        self._scanning_mode = BluetoothScanningMode.ACTIVE

    @hass_callback
    def async_setup(self) -> None:
        """Set up the bluetooth manager."""
        models.HA_BLEAK_SCANNER = self.scanner = HaBleakScanner()

    @hass_callback
    def async_get_scanner(self) -> HaBleakScannerWrapper:
        """Get the scanner."""
        return HaBleakScannerWrapper()

    @hass_callback
    def async_start_reload(self) -> None:
        """Start reloading."""
        self._reloading = True

    async def async_start(
        self, scanning_mode: BluetoothScanningMode, adapter: str | None
    ) -> None:
        """Set up BT Discovery."""
        assert self.scanner is not None
        self._adapter = adapter
        self._scanning_mode = scanning_mode
        if self._reloading:
            # On reload, we need to reset the scanner instance
            # since the devices in its history may not be reachable
            # anymore.
            self.scanner.async_reset()
            self._integration_matcher.async_clear_history()
            self._reloading = False
        scanner_kwargs = {"scanning_mode": SCANNING_MODE_TO_BLEAK[scanning_mode]}
        if adapter and adapter not in DEFAULT_ADAPTERS:
            scanner_kwargs["adapter"] = adapter
        _LOGGER.debug("Initializing bluetooth scanner with %s", scanner_kwargs)
        try:
            self.scanner.async_setup(**scanner_kwargs)
        except (FileNotFoundError, BleakError) as ex:
            raise RuntimeError(f"Failed to initialize Bluetooth: {ex}") from ex
        install_multiple_bleak_catcher()
        # We have to start it right away as some integrations might
        # need it straight away.
        _LOGGER.debug("Starting bluetooth scanner")
        self.scanner.register_detection_callback(self.scanner.async_callback_dispatcher)
        self._cancel_device_detected = self.scanner.async_register_callback(
            self._device_detected, {}
        )
        try:
            async with async_timeout.timeout(START_TIMEOUT):
                await self.scanner.start()  # type: ignore[no-untyped-call]
        except InvalidMessageError as ex:
            self._async_cancel_scanner_callback()
            _LOGGER.debug("Invalid DBus message received: %s", ex, exc_info=True)
            raise ConfigEntryNotReady(
                f"Invalid DBus message received: {ex}; try restarting `dbus`"
            ) from ex
        except BrokenPipeError as ex:
            self._async_cancel_scanner_callback()
            _LOGGER.debug("DBus connection broken: %s", ex, exc_info=True)
            if is_docker_env():
                raise ConfigEntryNotReady(
                    f"DBus connection broken: {ex}; try restarting `bluetooth`, `dbus`, and finally the docker container"
                ) from ex
            raise ConfigEntryNotReady(
                f"DBus connection broken: {ex}; try restarting `bluetooth` and `dbus`"
            ) from ex
        except FileNotFoundError as ex:
            self._async_cancel_scanner_callback()
            _LOGGER.debug(
                "FileNotFoundError while starting bluetooth: %s", ex, exc_info=True
            )
            if is_docker_env():
                raise ConfigEntryNotReady(
                    f"DBus service not found; docker config may be missing `-v /run/dbus:/run/dbus:ro`: {ex}"
                ) from ex
            raise ConfigEntryNotReady(
                f"DBus service not found; make sure the DBus socket is available to Home Assistant: {ex}"
            ) from ex
        except asyncio.TimeoutError as ex:
            self._async_cancel_scanner_callback()
            raise ConfigEntryNotReady(
                f"Timed out starting Bluetooth after {START_TIMEOUT} seconds"
            ) from ex
        except BleakError as ex:
            self._async_cancel_scanner_callback()
            _LOGGER.debug("BleakError while starting bluetooth: %s", ex, exc_info=True)
            raise ConfigEntryNotReady(f"Failed to start Bluetooth: {ex}") from ex
        self.async_setup_unavailable_tracking()
        self._async_setup_scanner_watchdog()
        self._cancel_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_hass_stopping
        )

    @hass_callback
    def _async_setup_scanner_watchdog(self) -> None:
        """If Dbus gets restarted or updated, we need to restart the scanner."""
        self._last_detection = MONOTONIC_TIME()
        self._cancel_watchdog = async_track_time_interval(
            self.hass, self._async_scanner_watchdog, SCANNER_WATCHDOG_INTERVAL
        )

    async def _async_scanner_watchdog(self, now: datetime) -> None:
        """Check if the scanner is running."""
        time_since_last_detection = MONOTONIC_TIME() - self._last_detection
        if time_since_last_detection < SCANNER_WATCHDOG_TIMEOUT:
            return
        _LOGGER.info(
            "Bluetooth scanner has gone quiet for %s, restarting",
            SCANNER_WATCHDOG_INTERVAL,
        )
        async with self.start_stop_lock:
            self.async_start_reload()
            await self.async_stop()
            await self.async_start(self._scanning_mode, self._adapter)

    @hass_callback
    def async_setup_unavailable_tracking(self) -> None:
        """Set up the unavailable tracking."""

        @hass_callback
        def _async_check_unavailable(now: datetime) -> None:
            """Watch for unavailable devices."""
            scanner = self.scanner
            assert scanner is not None
            history = set(scanner.history)
            active = {device.address for device in scanner.discovered_devices}
            disappeared = history.difference(active)
            for address in disappeared:
                del scanner.history[address]
                if not (callbacks := self._unavailable_callbacks.get(address)):
                    continue
                for callback in callbacks:
                    try:
                        callback(address)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception("Error in unavailable callback")

        self._cancel_unavailable_tracking = async_track_time_interval(
            self.hass,
            _async_check_unavailable,
            timedelta(seconds=UNAVAILABLE_TRACK_SECONDS),
        )

    @hass_callback
    def _device_detected(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Handle a detected device."""
        self._last_detection = MONOTONIC_TIME()
        matched_domains = self._integration_matcher.match_domains(
            device, advertisement_data
        )
        _LOGGER.debug(
            "Device detected: %s with advertisement_data: %s matched domains: %s",
            device.address,
            advertisement_data,
            matched_domains,
        )

        if not matched_domains and not self._callbacks:
            return

        service_info: BluetoothServiceInfoBleak | None = None
        for callback, matcher in self._callbacks:
            if matcher is None or ble_device_matches(
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
    def async_track_unavailable(
        self, callback: Callable[[str], None], address: str
    ) -> Callable[[], None]:
        """Register a callback."""
        self._unavailable_callbacks.setdefault(address, []).append(callback)

        @hass_callback
        def _async_remove_callback() -> None:
            self._unavailable_callbacks[address].remove(callback)
            if not self._unavailable_callbacks[address]:
                del self._unavailable_callbacks[address]

        return _async_remove_callback

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
            and self.scanner
            and (device_adv_data := self.scanner.history.get(address))
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
        if self.scanner and (ble_adv := self.scanner.history.get(address)):
            return ble_adv[0]
        return None

    @hass_callback
    def async_address_present(self, address: str) -> bool:
        """Return if the address is present."""
        return bool(self.scanner and address in self.scanner.history)

    @hass_callback
    def async_discovered_service_info(self) -> list[BluetoothServiceInfoBleak]:
        """Return if the address is present."""
        assert self.scanner is not None
        return [
            BluetoothServiceInfoBleak.from_advertisement(*device_adv, SOURCE_LOCAL)
            for device_adv in self.scanner.history.values()
        ]

    async def _async_hass_stopping(self, event: Event) -> None:
        """Stop the Bluetooth integration at shutdown."""
        self._cancel_stop = None
        await self.async_stop()

    @hass_callback
    def _async_cancel_scanner_callback(self) -> None:
        """Cancel the scanner callback."""
        if self._cancel_device_detected:
            self._cancel_device_detected()
            self._cancel_device_detected = None

    async def async_stop(self) -> None:
        """Stop bluetooth discovery."""
        _LOGGER.debug("Stopping bluetooth discovery")
        if self._cancel_watchdog:
            self._cancel_watchdog()
            self._cancel_watchdog = None
        self._async_cancel_scanner_callback()
        if self._cancel_unavailable_tracking:
            self._cancel_unavailable_tracking()
            self._cancel_unavailable_tracking = None
        if self._cancel_stop:
            self._cancel_stop()
            self._cancel_stop = None
        if self.scanner:
            try:
                await self.scanner.stop()  # type: ignore[no-untyped-call]
            except BleakError as ex:
                # This is not fatal, and they may want to reload
                # the config entry to restart the scanner if they
                # change the bluetooth dongle.
                _LOGGER.error("Error stopping scanner: %s", ex)
        uninstall_multiple_bleak_catcher()

    @hass_callback
    def async_rediscover_address(self, address: str) -> None:
        """Trigger discovery of devices which have already been seen."""
        self._integration_matcher.async_clear_address(address)

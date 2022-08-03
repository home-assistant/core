"""The bluetooth integration."""
from __future__ import annotations

import asyncio
from asyncio import Future
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import TYPE_CHECKING, Final

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
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.loader import async_get_bluetooth
from homeassistant.util.package import is_docker_env

from . import models
from .const import CONF_ADAPTER, DEFAULT_ADAPTERS, DOMAIN
from .match import (
    ADDRESS,
    BluetoothCallbackMatcher,
    IntegrationMatcher,
    ble_device_matches,
)
from .models import HaBleakScanner, HaBleakScannerWrapper
from .usage import install_multiple_bleak_catcher, uninstall_multiple_bleak_catcher
from .util import async_get_bluetooth_adapters

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData

    from homeassistant.helpers.typing import ConfigType


_LOGGER = logging.getLogger(__name__)


UNAVAILABLE_TRACK_SECONDS: Final = 60 * 5
START_TIMEOUT = 9

SOURCE_LOCAL: Final = "local"


@dataclass
class BluetoothServiceInfoBleak(BluetoothServiceInfo):
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
    ) -> BluetoothServiceInfoBleak:
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


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


SCANNING_MODE_TO_BLEAK = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]


@hass_callback
def async_get_scanner(hass: HomeAssistant) -> HaBleakScannerWrapper:
    """Return a HaBleakScannerWrapper.

    This is a wrapper around our BleakScanner singleton that allows
    multiple integrations to share the same BleakScanner.
    """
    if DOMAIN not in hass.data:
        raise RuntimeError("Bluetooth integration not loaded")
    manager: BluetoothManager = hass.data[DOMAIN]
    return manager.async_get_scanner()


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
    mode: BluetoothScanningMode,
) -> Callable[[], None]:
    """Register to receive a callback on bluetooth change.

    mode is currently not used as we only support active scanning.
    Passive scanning will be available in the future. The flag
    is required to be present to avoid a future breaking change
    when we support passive scanning.

    Returns a callback that can be used to cancel the registration.
    """
    manager: BluetoothManager = hass.data[DOMAIN]
    return manager.async_register_callback(callback, match_dict)


async def async_process_advertisements(
    hass: HomeAssistant,
    callback: ProcessAdvertisementCallback,
    match_dict: BluetoothCallbackMatcher,
    mode: BluetoothScanningMode,
    timeout: int,
) -> BluetoothServiceInfoBleak:
    """Process advertisements until callback returns true or timeout expires."""
    done: Future[BluetoothServiceInfoBleak] = Future()

    @hass_callback
    def _async_discovered_device(
        service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        if callback(service_info):
            done.set_result(service_info)

    unload = async_register_callback(hass, _async_discovered_device, match_dict, mode)

    try:
        async with async_timeout.timeout(timeout):
            return await done
    finally:
        unload()


@hass_callback
def async_track_unavailable(
    hass: HomeAssistant,
    callback: Callable[[str], None],
    address: str,
) -> Callable[[], None]:
    """Register to receive a callback when an address is unavailable.

    Returns a callback that can be used to cancel the registration.
    """
    manager: BluetoothManager = hass.data[DOMAIN]
    return manager.async_track_unavailable(callback, address)


async def _async_has_bluetooth_adapter() -> bool:
    """Return if the device has a bluetooth adapter."""
    return bool(await async_get_bluetooth_adapters())


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the bluetooth integration."""
    integration_matcher = IntegrationMatcher(await async_get_bluetooth(hass))
    manager = BluetoothManager(hass, integration_matcher)
    manager.async_setup()
    hass.data[DOMAIN] = manager
    # The config entry is responsible for starting the manager
    # if its enabled

    if hass.config_entries.async_entries(DOMAIN):
        return True
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )
    elif await _async_has_bluetooth_adapter():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                data={},
            )
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up the bluetooth integration from a config entry."""
    manager: BluetoothManager = hass.data[DOMAIN]
    await manager.async_start(
        BluetoothScanningMode.ACTIVE, entry.options.get(CONF_ADAPTER)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Handle options update."""
    manager: BluetoothManager = hass.data[DOMAIN]
    manager.async_start_reload()
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    manager: BluetoothManager = hass.data[DOMAIN]
    await manager.async_stop()
    return True


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
        self._cancel_device_detected: CALLBACK_TYPE | None = None
        self._cancel_unavailable_tracking: CALLBACK_TYPE | None = None
        self._unavailable_callbacks: dict[str, list[Callable[[str], None]]] = {}
        self._callbacks: list[
            tuple[BluetoothCallback, BluetoothCallbackMatcher | None]
        ] = []
        self._reloading = False

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
            self._cancel_device_detected()
            _LOGGER.debug("Invalid DBus message received: %s", ex, exc_info=True)
            raise ConfigEntryNotReady(
                f"Invalid DBus message received: {ex}; try restarting `dbus`"
            ) from ex
        except BrokenPipeError as ex:
            self._cancel_device_detected()
            _LOGGER.debug("DBus connection broken: %s", ex, exc_info=True)
            if is_docker_env():
                raise ConfigEntryNotReady(
                    f"DBus connection broken: {ex}; try restarting `bluetooth`, `dbus`, and finally the docker container"
                ) from ex
            raise ConfigEntryNotReady(
                f"DBus connection broken: {ex}; try restarting `bluetooth` and `dbus`"
            ) from ex
        except FileNotFoundError as ex:
            self._cancel_device_detected()
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
            self._cancel_device_detected()
            raise ConfigEntryNotReady(
                f"Timed out starting Bluetooth after {START_TIMEOUT} seconds"
            ) from ex
        except BleakError as ex:
            self._cancel_device_detected()
            _LOGGER.debug("BleakError while starting bluetooth: %s", ex, exc_info=True)
            raise ConfigEntryNotReady(f"Failed to start Bluetooth: {ex}") from ex
        self.async_setup_unavailable_tracking()
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)

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

    async def async_stop(self, event: Event | None = None) -> None:
        """Stop bluetooth discovery."""
        if self._cancel_device_detected:
            self._cancel_device_detected()
            self._cancel_device_detected = None
        if self._cancel_unavailable_tracking:
            self._cancel_unavailable_tracking()
            self._cancel_unavailable_tracking = None
        if self.scanner:
            try:
                await self.scanner.stop()  # type: ignore[no-untyped-call]
            except BleakError as ex:
                # This is not fatal, and they may want to reload
                # the config entry to restart the scanner if they
                # change the bluetooth dongle.
                _LOGGER.error("Error stopping scanner: %s", ex)
        uninstall_multiple_bleak_catcher()

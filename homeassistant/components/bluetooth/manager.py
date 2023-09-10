"""The bluetooth integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
import itertools
import logging
from typing import TYPE_CHECKING, Any, Final

from bleak.backends.scanner import AdvertisementDataCallback
from bleak_retry_connector import NO_RSSI_VALUE, RSSI_SWITCH_THRESHOLD, BleakSlotManager
from bluetooth_adapters import (
    ADAPTER_ADDRESS,
    ADAPTER_PASSIVE_SCAN,
    AdapterDetails,
    BluetoothAdapters,
)

from homeassistant import config_entries
from homeassistant.components.logger import EVENT_LOGGING_CHANGED
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import monotonic_time_coarse

from .advertisement_tracker import (
    TRACKER_BUFFERING_WOBBLE_SECONDS,
    AdvertisementTracker,
)
from .base_scanner import BaseHaScanner, BluetoothScannerDevice
from .const import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    UNAVAILABLE_TRACK_SECONDS,
)
from .match import (
    ADDRESS,
    CALLBACK,
    CONNECTABLE,
    BluetoothCallbackMatcher,
    BluetoothCallbackMatcherIndex,
    BluetoothCallbackMatcherWithCallback,
    IntegrationMatcher,
    ble_device_matches,
)
from .models import BluetoothCallback, BluetoothChange, BluetoothServiceInfoBleak
from .storage import BluetoothStorage
from .usage import install_multiple_bleak_catcher, uninstall_multiple_bleak_catcher
from .util import async_load_history_from_system

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData


FILTER_UUIDS: Final = "UUIDs"

APPLE_MFR_ID: Final = 76
APPLE_IBEACON_START_BYTE: Final = 0x02  # iBeacon (tilt_ble)
APPLE_HOMEKIT_START_BYTE: Final = 0x06  # homekit_controller
APPLE_DEVICE_ID_START_BYTE: Final = 0x10  # bluetooth_le_tracker
APPLE_HOMEKIT_NOTIFY_START_BYTE: Final = 0x11  # homekit_controller
APPLE_START_BYTES_WANTED: Final = {
    APPLE_IBEACON_START_BYTE,
    APPLE_HOMEKIT_START_BYTE,
    APPLE_HOMEKIT_NOTIFY_START_BYTE,
    APPLE_DEVICE_ID_START_BYTE,
}

MONOTONIC_TIME: Final = monotonic_time_coarse

_LOGGER = logging.getLogger(__name__)


def _dispatch_bleak_callback(
    callback: AdvertisementDataCallback | None,
    filters: dict[str, set[str]],
    device: BLEDevice,
    advertisement_data: AdvertisementData,
) -> None:
    """Dispatch the callback."""
    if not callback:
        # Callback destroyed right before being called, ignore
        return

    if (uuids := filters.get(FILTER_UUIDS)) and not uuids.intersection(
        advertisement_data.service_uuids
    ):
        return

    try:
        callback(device, advertisement_data)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error in callback: %s", callback)


class BluetoothManager:
    """Manage Bluetooth."""

    __slots__ = (
        "hass",
        "_integration_matcher",
        "_cancel_unavailable_tracking",
        "_cancel_logging_listener",
        "_advertisement_tracker",
        "_unavailable_callbacks",
        "_connectable_unavailable_callbacks",
        "_callback_index",
        "_bleak_callbacks",
        "_all_history",
        "_connectable_history",
        "_non_connectable_scanners",
        "_connectable_scanners",
        "_adapters",
        "_sources",
        "_bluetooth_adapters",
        "storage",
        "slot_manager",
        "_debug",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        integration_matcher: IntegrationMatcher,
        bluetooth_adapters: BluetoothAdapters,
        storage: BluetoothStorage,
        slot_manager: BleakSlotManager,
    ) -> None:
        """Init bluetooth manager."""
        self.hass = hass
        self._integration_matcher = integration_matcher
        self._cancel_unavailable_tracking: CALLBACK_TYPE | None = None
        self._cancel_logging_listener: CALLBACK_TYPE | None = None

        self._advertisement_tracker = AdvertisementTracker()

        self._unavailable_callbacks: dict[
            str, list[Callable[[BluetoothServiceInfoBleak], None]]
        ] = {}
        self._connectable_unavailable_callbacks: dict[
            str, list[Callable[[BluetoothServiceInfoBleak], None]]
        ] = {}

        self._callback_index = BluetoothCallbackMatcherIndex()
        self._bleak_callbacks: list[
            tuple[AdvertisementDataCallback, dict[str, set[str]]]
        ] = []
        self._all_history: dict[str, BluetoothServiceInfoBleak] = {}
        self._connectable_history: dict[str, BluetoothServiceInfoBleak] = {}
        self._non_connectable_scanners: list[BaseHaScanner] = []
        self._connectable_scanners: list[BaseHaScanner] = []
        self._adapters: dict[str, AdapterDetails] = {}
        self._sources: dict[str, BaseHaScanner] = {}
        self._bluetooth_adapters = bluetooth_adapters
        self.storage = storage
        self.slot_manager = slot_manager
        self._debug = _LOGGER.isEnabledFor(logging.DEBUG)

    @property
    def supports_passive_scan(self) -> bool:
        """Return if passive scan is supported."""
        return any(adapter[ADAPTER_PASSIVE_SCAN] for adapter in self._adapters.values())

    def async_scanner_count(self, connectable: bool = True) -> int:
        """Return the number of scanners."""
        if connectable:
            return len(self._connectable_scanners)
        return len(self._connectable_scanners) + len(self._non_connectable_scanners)

    async def async_diagnostics(self) -> dict[str, Any]:
        """Diagnostics for the manager."""
        scanner_diagnostics = await asyncio.gather(
            *[
                scanner.async_diagnostics()
                for scanner in itertools.chain(
                    self._non_connectable_scanners, self._connectable_scanners
                )
            ]
        )
        return {
            "adapters": self._adapters,
            "slot_manager": self.slot_manager.diagnostics(),
            "scanners": scanner_diagnostics,
            "connectable_history": [
                service_info.as_dict()
                for service_info in self._connectable_history.values()
            ],
            "all_history": [
                service_info.as_dict() for service_info in self._all_history.values()
            ],
            "advertisement_tracker": self._advertisement_tracker.async_diagnostics(),
        }

    def _find_adapter_by_address(self, address: str) -> str | None:
        for adapter, details in self._adapters.items():
            if details[ADAPTER_ADDRESS] == address:
                return adapter
        return None

    @hass_callback
    def async_scanner_by_source(self, source: str) -> BaseHaScanner | None:
        """Return the scanner for a source."""
        return self._sources.get(source)

    async def async_get_bluetooth_adapters(
        self, cached: bool = True
    ) -> dict[str, AdapterDetails]:
        """Get bluetooth adapters."""
        if not self._adapters or not cached:
            if not cached:
                await self._bluetooth_adapters.refresh()
            self._adapters = self._bluetooth_adapters.adapters
        return self._adapters

    async def async_get_adapter_from_address(self, address: str) -> str | None:
        """Get adapter from address."""
        if adapter := self._find_adapter_by_address(address):
            return adapter
        await self._bluetooth_adapters.refresh()
        self._adapters = self._bluetooth_adapters.adapters
        return self._find_adapter_by_address(address)

    @hass_callback
    def _async_logging_changed(self, event: Event) -> None:
        """Handle logging change."""
        self._debug = _LOGGER.isEnabledFor(logging.DEBUG)

    async def async_setup(self) -> None:
        """Set up the bluetooth manager."""
        await self._bluetooth_adapters.refresh()
        install_multiple_bleak_catcher()
        self._all_history, self._connectable_history = async_load_history_from_system(
            self._bluetooth_adapters, self.storage
        )
        self._cancel_logging_listener = self.hass.bus.async_listen(
            EVENT_LOGGING_CHANGED, self._async_logging_changed
        )
        self.async_setup_unavailable_tracking()
        seen: set[str] = set()
        for address, service_info in itertools.chain(
            self._connectable_history.items(), self._all_history.items()
        ):
            if address in seen:
                continue
            seen.add(address)
            self._async_trigger_matching_discovery(service_info)

    @hass_callback
    def async_stop(self, event: Event) -> None:
        """Stop the Bluetooth integration at shutdown."""
        _LOGGER.debug("Stopping bluetooth manager")
        if self._cancel_unavailable_tracking:
            self._cancel_unavailable_tracking()
            self._cancel_unavailable_tracking = None
        if self._cancel_logging_listener:
            self._cancel_logging_listener()
            self._cancel_logging_listener = None
        uninstall_multiple_bleak_catcher()

    @hass_callback
    def async_scanner_devices_by_address(
        self, address: str, connectable: bool
    ) -> list[BluetoothScannerDevice]:
        """Get BluetoothScannerDevice by address."""
        if not connectable:
            scanners: Iterable[BaseHaScanner] = itertools.chain(
                self._connectable_scanners, self._non_connectable_scanners
            )
        else:
            scanners = self._connectable_scanners
        return [
            BluetoothScannerDevice(scanner, *device_adv)
            for scanner in scanners
            if (
                device_adv := scanner.discovered_devices_and_advertisement_data.get(
                    address
                )
            )
        ]

    @hass_callback
    def _async_all_discovered_addresses(self, connectable: bool) -> Iterable[str]:
        """Return all of discovered addresses.

        Include addresses from all the scanners including duplicates.
        """
        yield from itertools.chain.from_iterable(
            scanner.discovered_devices_and_advertisement_data
            for scanner in self._connectable_scanners
        )
        if not connectable:
            yield from itertools.chain.from_iterable(
                scanner.discovered_devices_and_advertisement_data
                for scanner in self._non_connectable_scanners
            )

    @hass_callback
    def async_discovered_devices(self, connectable: bool) -> list[BLEDevice]:
        """Return all of combined best path to discovered from all the scanners."""
        histories = self._connectable_history if connectable else self._all_history
        return [history.device for history in histories.values()]

    @hass_callback
    def async_setup_unavailable_tracking(self) -> None:
        """Set up the unavailable tracking."""
        self._cancel_unavailable_tracking = async_track_time_interval(
            self.hass,
            self._async_check_unavailable,
            timedelta(seconds=UNAVAILABLE_TRACK_SECONDS),
            name="Bluetooth manager unavailable tracking",
        )

    @hass_callback
    def _async_check_unavailable(self, now: datetime) -> None:
        """Watch for unavailable devices and cleanup state history."""
        monotonic_now = MONOTONIC_TIME()
        connectable_history = self._connectable_history
        all_history = self._all_history
        tracker = self._advertisement_tracker
        intervals = tracker.intervals

        for connectable in (True, False):
            if connectable:
                unavailable_callbacks = self._connectable_unavailable_callbacks
            else:
                unavailable_callbacks = self._unavailable_callbacks
            history = connectable_history if connectable else all_history
            disappeared = set(history).difference(
                self._async_all_discovered_addresses(connectable)
            )
            for address in disappeared:
                if not connectable:
                    #
                    # For non-connectable devices we also check the device has exceeded
                    # the advertising interval before we mark it as unavailable
                    # since it may have gone to sleep and since we do not need an active
                    # connection to it we can only determine its availability
                    # by the lack of advertisements
                    if advertising_interval := intervals.get(address):
                        advertising_interval += TRACKER_BUFFERING_WOBBLE_SECONDS
                    else:
                        advertising_interval = (
                            FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
                        )
                    time_since_seen = monotonic_now - all_history[address].time
                    if time_since_seen <= advertising_interval:
                        continue

                    # The second loop (connectable=False) is responsible for removing
                    # the device from all the interval tracking since it is no longer
                    # available for both connectable and non-connectable
                    tracker.async_remove_address(address)
                    self._integration_matcher.async_clear_address(address)
                    self._async_dismiss_discoveries(address)

                service_info = history.pop(address)

                if not (callbacks := unavailable_callbacks.get(address)):
                    continue

                for callback in callbacks:
                    try:
                        callback(service_info)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception("Error in unavailable callback")

    def _async_dismiss_discoveries(self, address: str) -> None:
        """Dismiss all discoveries for the given address."""
        for flow in self.hass.config_entries.flow.async_progress_by_init_data_type(
            BluetoothServiceInfoBleak,
            lambda service_info: bool(service_info.address == address),
        ):
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

    def _prefer_previous_adv_from_different_source(
        self,
        old: BluetoothServiceInfoBleak,
        new: BluetoothServiceInfoBleak,
    ) -> bool:
        """Prefer previous advertisement from a different source if it is better."""
        if new.time - old.time > (
            stale_seconds := self._advertisement_tracker.intervals.get(
                new.address, FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
            )
        ):
            # If the old advertisement is stale, any new advertisement is preferred
            if self._debug:
                _LOGGER.debug(
                    (
                        "%s (%s): Switching from %s to %s (time elapsed:%s > stale"
                        " seconds:%s)"
                    ),
                    new.name,
                    new.address,
                    self._async_describe_source(old),
                    self._async_describe_source(new),
                    new.time - old.time,
                    stale_seconds,
                )
            return False
        if (new.rssi or NO_RSSI_VALUE) - RSSI_SWITCH_THRESHOLD > (
            old.rssi or NO_RSSI_VALUE
        ):
            # If new advertisement is RSSI_SWITCH_THRESHOLD more,
            # the new one is preferred.
            if self._debug:
                _LOGGER.debug(
                    (
                        "%s (%s): Switching from %s to %s (new rssi:%s - threshold:%s >"
                        " old rssi:%s)"
                    ),
                    new.name,
                    new.address,
                    self._async_describe_source(old),
                    self._async_describe_source(new),
                    new.rssi,
                    RSSI_SWITCH_THRESHOLD,
                    old.rssi,
                )
            return False
        return True

    @hass_callback
    def scanner_adv_received(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Handle a new advertisement from any scanner.

        Callbacks from all the scanners arrive here.
        """

        # Pre-filter noisy apple devices as they can account for 20-35% of the
        # traffic on a typical network.
        if (
            (manufacturer_data := service_info.manufacturer_data)
            and APPLE_MFR_ID in manufacturer_data
            and manufacturer_data[APPLE_MFR_ID][0] not in APPLE_START_BYTES_WANTED
            and len(manufacturer_data) == 1
            and not service_info.service_data
        ):
            return

        address = service_info.device.address
        all_history = self._all_history
        connectable = service_info.connectable
        connectable_history = self._connectable_history
        old_connectable_service_info = connectable and connectable_history.get(address)
        source = service_info.source
        # This logic is complex due to the many combinations of scanners
        # that are supported.
        #
        # We need to handle multiple connectable and non-connectable scanners
        # and we need to handle the case where a device is connectable on one scanner
        # but not on another.
        #
        # The device may also be connectable only by a scanner that has worse
        # signal strength than a non-connectable scanner.
        #
        # all_history - the history of all advertisements from all scanners with the
        #               best advertisement from each scanner
        # connectable_history - the history of all connectable advertisements from all
        #                       scanners with the best advertisement from each
        #                       connectable scanner
        #
        if (
            (old_service_info := all_history.get(address))
            and source != old_service_info.source
            and (scanner := self._sources.get(old_service_info.source))
            and scanner.scanning
            and self._prefer_previous_adv_from_different_source(
                old_service_info, service_info
            )
        ):
            # If we are rejecting the new advertisement and the device is connectable
            # but not in the connectable history or the connectable source is the same
            # as the new source, we need to add it to the connectable history
            if connectable:
                if old_connectable_service_info and (
                    # If its the same as the preferred source, we are done
                    # as we know we prefer the old advertisement
                    # from the check above
                    (old_connectable_service_info is old_service_info)
                    # If the old connectable source is different from the preferred
                    # source, we need to check it as well to see if we prefer
                    # the old connectable advertisement
                    or (
                        source != old_connectable_service_info.source
                        and (
                            connectable_scanner := self._sources.get(
                                old_connectable_service_info.source
                            )
                        )
                        and connectable_scanner.scanning
                        and self._prefer_previous_adv_from_different_source(
                            old_connectable_service_info, service_info
                        )
                    )
                ):
                    return

                connectable_history[address] = service_info

            return

        if connectable:
            connectable_history[address] = service_info

        all_history[address] = service_info

        # Track advertisement intervals to determine when we need to
        # switch adapters or mark a device as unavailable
        tracker = self._advertisement_tracker
        if (last_source := tracker.sources.get(address)) and last_source != source:
            # Source changed, remove the old address from the tracker
            tracker.async_remove_address(address)
        if address not in tracker.intervals:
            tracker.async_collect(service_info)

        # If the advertisement data is the same as the last time we saw it, we
        # don't need to do anything else unless its connectable and we are missing
        # connectable history for the device so we can make it available again
        # after unavailable callbacks.
        if (
            # Ensure its not a connectable device missing from connectable history
            not (connectable and not old_connectable_service_info)
            # Than check if advertisement data is the same
            and old_service_info
            and not (
                service_info.manufacturer_data != old_service_info.manufacturer_data
                or service_info.service_data != old_service_info.service_data
                or service_info.service_uuids != old_service_info.service_uuids
                or service_info.name != old_service_info.name
            )
        ):
            return

        if not connectable and old_connectable_service_info:
            # Since we have a connectable path and our BleakClient will
            # route any connection attempts to the connectable path, we
            # mark the service_info as connectable so that the callbacks
            # will be called and the device can be discovered.
            service_info = BluetoothServiceInfoBleak(
                name=service_info.name,
                address=service_info.address,
                rssi=service_info.rssi,
                manufacturer_data=service_info.manufacturer_data,
                service_data=service_info.service_data,
                service_uuids=service_info.service_uuids,
                source=service_info.source,
                device=service_info.device,
                advertisement=service_info.advertisement,
                connectable=True,
                time=service_info.time,
            )

        matched_domains = self._integration_matcher.match_domains(service_info)
        if self._debug:
            _LOGGER.debug(
                "%s: %s %s match: %s",
                self._async_describe_source(service_info),
                address,
                service_info.advertisement,
                matched_domains,
            )

        if (connectable or old_connectable_service_info) and (
            bleak_callbacks := self._bleak_callbacks
        ):
            # Bleak callbacks must get a connectable device
            device = service_info.device
            advertisement_data = service_info.advertisement
            for callback_filters in bleak_callbacks:
                _dispatch_bleak_callback(*callback_filters, device, advertisement_data)

        for match in self._callback_index.match_callbacks(service_info):
            callback = match[CALLBACK]
            try:
                callback(service_info, BluetoothChange.ADVERTISEMENT)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error in bluetooth callback")

        for domain in matched_domains:
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_BLUETOOTH},
                service_info,
            )

    @hass_callback
    def _async_describe_source(self, service_info: BluetoothServiceInfoBleak) -> str:
        """Describe a source."""
        if scanner := self._sources.get(service_info.source):
            description = scanner.name
        else:
            description = service_info.source
        if service_info.connectable:
            description += " [connectable]"
        return description

    @hass_callback
    def async_track_unavailable(
        self,
        callback: Callable[[BluetoothServiceInfoBleak], None],
        address: str,
        connectable: bool,
    ) -> Callable[[], None]:
        """Register a callback."""
        if connectable:
            unavailable_callbacks = self._connectable_unavailable_callbacks
        else:
            unavailable_callbacks = self._unavailable_callbacks
        unavailable_callbacks.setdefault(address, []).append(callback)

        @hass_callback
        def _async_remove_callback() -> None:
            unavailable_callbacks[address].remove(callback)
            if not unavailable_callbacks[address]:
                del unavailable_callbacks[address]

        return _async_remove_callback

    @hass_callback
    def async_register_callback(
        self,
        callback: BluetoothCallback,
        matcher: BluetoothCallbackMatcher | None,
    ) -> Callable[[], None]:
        """Register a callback."""
        callback_matcher = BluetoothCallbackMatcherWithCallback(callback=callback)
        if not matcher:
            callback_matcher[CONNECTABLE] = True
        else:
            # We could write out every item in the typed dict here
            # but that would be a bit inefficient and verbose.
            callback_matcher.update(matcher)
            callback_matcher[CONNECTABLE] = matcher.get(CONNECTABLE, True)

        connectable = callback_matcher[CONNECTABLE]
        self._callback_index.add_callback_matcher(callback_matcher)

        @hass_callback
        def _async_remove_callback() -> None:
            self._callback_index.remove_callback_matcher(callback_matcher)

        # If we have history for the subscriber, we can trigger the callback
        # immediately with the last packet so the subscriber can see the
        # device.
        history = self._connectable_history if connectable else self._all_history
        service_infos: Iterable[BluetoothServiceInfoBleak] = []
        if address := callback_matcher.get(ADDRESS):
            if service_info := history.get(address):
                service_infos = [service_info]
        else:
            service_infos = history.values()

        for service_info in service_infos:
            if ble_device_matches(callback_matcher, service_info):
                try:
                    callback(service_info, BluetoothChange.ADVERTISEMENT)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error in bluetooth callback")

        return _async_remove_callback

    @hass_callback
    def async_ble_device_from_address(
        self, address: str, connectable: bool
    ) -> BLEDevice | None:
        """Return the BLEDevice if present."""
        histories = self._connectable_history if connectable else self._all_history
        if history := histories.get(address):
            return history.device
        return None

    @hass_callback
    def async_address_present(self, address: str, connectable: bool) -> bool:
        """Return if the address is present."""
        histories = self._connectable_history if connectable else self._all_history
        return address in histories

    @hass_callback
    def async_discovered_service_info(
        self, connectable: bool
    ) -> Iterable[BluetoothServiceInfoBleak]:
        """Return all the discovered services info."""
        histories = self._connectable_history if connectable else self._all_history
        return histories.values()

    @hass_callback
    def async_last_service_info(
        self, address: str, connectable: bool
    ) -> BluetoothServiceInfoBleak | None:
        """Return the last service info for an address."""
        histories = self._connectable_history if connectable else self._all_history
        return histories.get(address)

    def _async_trigger_matching_discovery(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Trigger discovery for matching domains."""
        for domain in self._integration_matcher.match_domains(service_info):
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_BLUETOOTH},
                service_info,
            )

    @hass_callback
    def async_rediscover_address(self, address: str) -> None:
        """Trigger discovery of devices which have already been seen."""
        self._integration_matcher.async_clear_address(address)
        if service_info := self._connectable_history.get(address):
            self._async_trigger_matching_discovery(service_info)
            return
        if service_info := self._all_history.get(address):
            self._async_trigger_matching_discovery(service_info)

    def async_register_scanner(
        self,
        scanner: BaseHaScanner,
        connectable: bool,
        connection_slots: int | None = None,
    ) -> CALLBACK_TYPE:
        """Register a new scanner."""
        _LOGGER.debug("Registering scanner %s", scanner.name)
        if connectable:
            scanners = self._connectable_scanners
        else:
            scanners = self._non_connectable_scanners

        def _unregister_scanner() -> None:
            _LOGGER.debug("Unregistering scanner %s", scanner.name)
            self._advertisement_tracker.async_remove_source(scanner.source)
            scanners.remove(scanner)
            del self._sources[scanner.source]
            if connection_slots:
                self.slot_manager.remove_adapter(scanner.adapter)

        scanners.append(scanner)
        self._sources[scanner.source] = scanner
        if connection_slots:
            self.slot_manager.register_adapter(scanner.adapter, connection_slots)
        return _unregister_scanner

    @hass_callback
    def async_register_bleak_callback(
        self, callback: AdvertisementDataCallback, filters: dict[str, set[str]]
    ) -> CALLBACK_TYPE:
        """Register a callback."""
        callback_entry = (callback, filters)
        self._bleak_callbacks.append(callback_entry)

        @hass_callback
        def _remove_callback() -> None:
            self._bleak_callbacks.remove(callback_entry)

        # Replay the history since otherwise we miss devices
        # that were already discovered before the callback was registered
        # or we are in passive mode
        for history in self._connectable_history.values():
            _dispatch_bleak_callback(
                callback, filters, history.device, history.advertisement
            )

        return _remove_callback

    @hass_callback
    def async_release_connection_slot(self, device: BLEDevice) -> None:
        """Release a connection slot."""
        self.slot_manager.release_slot(device)

    @hass_callback
    def async_allocate_connection_slot(self, device: BLEDevice) -> bool:
        """Allocate a connection slot."""
        return self.slot_manager.allocate_slot(device)

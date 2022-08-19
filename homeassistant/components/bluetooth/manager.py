"""The bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
import itertools
import logging
from typing import TYPE_CHECKING, Final

from bleak.backends.scanner import AdvertisementDataCallback

from homeassistant import config_entries
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ADAPTER_ADDRESS,
    SOURCE_LOCAL,
    UNAVAILABLE_TRACK_SECONDS,
    AdapterDetails,
)
from .match import (
    ADDRESS,
    BluetoothCallbackMatcher,
    IntegrationMatcher,
    ble_device_matches,
)
from .models import BluetoothCallback, BluetoothChange, BluetoothServiceInfoBleak
from .usage import install_multiple_bleak_catcher, uninstall_multiple_bleak_catcher
from .util import async_get_bluetooth_adapters

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData

    from .scanner import HaScanner

FILTER_UUIDS: Final = "UUIDs"


RSSI_SWITCH_THRESHOLD = 6
STALE_ADVERTISEMENT_SECONDS = 180

_LOGGER = logging.getLogger(__name__)


@dataclass
class AdvertisementHistory:
    """Bluetooth advertisement history."""

    ble_device: BLEDevice
    advertisement_data: AdvertisementData
    time: float
    source: str


def _prefer_previous_adv(old: AdvertisementHistory, new: AdvertisementHistory) -> bool:
    """Prefer previous advertisement if it is better."""
    if new.time - old.time > STALE_ADVERTISEMENT_SECONDS:
        # If the old advertisement is stale, any new advertisement is preferred
        if new.source != old.source:
            _LOGGER.debug(
                "%s (%s): Switching from %s to %s (time_elapsed:%s > stale_seconds:%s)",
                new.advertisement_data.local_name,
                new.ble_device.address,
                old.source,
                new.source,
                new.time - old.time,
                STALE_ADVERTISEMENT_SECONDS,
            )
        return False
    if new.ble_device.rssi - RSSI_SWITCH_THRESHOLD > old.ble_device.rssi:
        # If new advertisement is RSSI_SWITCH_THRESHOLD more, the new one is preferred
        if new.source != old.source:
            _LOGGER.debug(
                "%s (%s): Switching from %s to %s (new_rssi:%s - threadshold:%s > old_rssi:%s)",
                new.advertisement_data.local_name,
                new.ble_device.address,
                old.source,
                new.source,
                new.ble_device.rssi,
                RSSI_SWITCH_THRESHOLD,
                old.ble_device.rssi,
            )
        return False
    # If the source is the different, the old one is preferred because its
    # not stale and its RSSI_SWITCH_THRESHOLD less than the new one
    return old.source != new.source


def _dispatch_bleak_callback(
    callback: AdvertisementDataCallback,
    filters: dict[str, set[str]],
    device: BLEDevice,
    advertisement_data: AdvertisementData,
) -> None:
    """Dispatch the callback."""
    if not callback:
        # Callback destroyed right before being called, ignore
        return  # type: ignore[unreachable] # pragma: no cover

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

    def __init__(
        self,
        hass: HomeAssistant,
        integration_matcher: IntegrationMatcher,
    ) -> None:
        """Init bluetooth manager."""
        self.hass = hass
        self._integration_matcher = integration_matcher
        self._cancel_unavailable_tracking: CALLBACK_TYPE | None = None
        self._unavailable_callbacks: dict[str, list[Callable[[str], None]]] = {}
        self._callbacks: list[
            tuple[BluetoothCallback, BluetoothCallbackMatcher | None]
        ] = []
        self._bleak_callbacks: list[
            tuple[AdvertisementDataCallback, dict[str, set[str]]]
        ] = []
        self.history: dict[str, AdvertisementHistory] = {}
        self._scanners: list[HaScanner] = []
        self._adapters: dict[str, AdapterDetails] = {}

    def _find_adapter_by_address(self, address: str) -> str | None:
        for adapter, details in self._adapters.items():
            if details[ADAPTER_ADDRESS] == address:
                return adapter
        return None

    async def async_get_bluetooth_adapters(self) -> dict[str, AdapterDetails]:
        """Get bluetooth adapters."""
        if not self._adapters:
            self._adapters = await async_get_bluetooth_adapters()
        return self._adapters

    async def async_get_adapter_from_address(self, address: str) -> str | None:
        """Get adapter from address."""
        if adapter := self._find_adapter_by_address(address):
            return adapter
        self._adapters = await async_get_bluetooth_adapters()
        return self._find_adapter_by_address(address)

    @hass_callback
    def async_setup(self) -> None:
        """Set up the bluetooth manager."""
        install_multiple_bleak_catcher()
        self.async_setup_unavailable_tracking()

    @hass_callback
    def async_stop(self, event: Event) -> None:
        """Stop the Bluetooth integration at shutdown."""
        _LOGGER.debug("Stopping bluetooth manager")
        if self._cancel_unavailable_tracking:
            self._cancel_unavailable_tracking()
            self._cancel_unavailable_tracking = None
        uninstall_multiple_bleak_catcher()

    @hass_callback
    def async_all_discovered_devices(self) -> Iterable[BLEDevice]:
        """Return all of discovered devices from all the scanners including duplicates."""
        return itertools.chain.from_iterable(
            scanner.discovered_devices for scanner in self._scanners
        )

    @hass_callback
    def async_discovered_devices(self) -> list[BLEDevice]:
        """Return all of combined best path to discovered from all the scanners."""
        return [history.ble_device for history in self.history.values()]

    @hass_callback
    def async_setup_unavailable_tracking(self) -> None:
        """Set up the unavailable tracking."""

        @hass_callback
        def _async_check_unavailable(now: datetime) -> None:
            """Watch for unavailable devices."""
            history_set = set(self.history)
            active_addresses = {
                device.address for device in self.async_all_discovered_devices()
            }
            disappeared = history_set.difference(active_addresses)
            for address in disappeared:
                del self.history[address]
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
    def scanner_adv_received(
        self,
        device: BLEDevice,
        advertisement_data: AdvertisementData,
        monotonic_time: float,
        source: str,
    ) -> None:
        """Handle a new advertisement from any scanner.

        Callbacks from all the scanners arrive here.

        In the future we will only process callbacks if

        - The device is not in the history
        - The RSSI is above a certain threshold better than
          than the source from the history or the timestamp
          in the history is older than 180s
        """
        new_history = AdvertisementHistory(
            device, advertisement_data, monotonic_time, source
        )
        if (old_history := self.history.get(device.address)) and _prefer_previous_adv(
            old_history, new_history
        ):
            return

        self.history[device.address] = new_history

        for callback_filters in self._bleak_callbacks:
            _dispatch_bleak_callback(*callback_filters, device, advertisement_data)

        matched_domains = self._integration_matcher.match_domains(
            device, advertisement_data
        )
        _LOGGER.debug(
            "%s: %s %s match: %s",
            source,
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
                        device, advertisement_data, source
                    )
                try:
                    callback(service_info, BluetoothChange.ADVERTISEMENT)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error in bluetooth callback")

        if not matched_domains:
            return
        if service_info is None:
            service_info = BluetoothServiceInfoBleak.from_advertisement(
                device, advertisement_data, source
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
            and (history := self.history.get(address))
        ):
            try:
                callback(
                    BluetoothServiceInfoBleak.from_advertisement(
                        history.ble_device, history.advertisement_data, SOURCE_LOCAL
                    ),
                    BluetoothChange.ADVERTISEMENT,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error in bluetooth callback")

        return _async_remove_callback

    @hass_callback
    def async_ble_device_from_address(self, address: str) -> BLEDevice | None:
        """Return the BLEDevice if present."""
        if history := self.history.get(address):
            return history.ble_device
        return None

    @hass_callback
    def async_address_present(self, address: str) -> bool:
        """Return if the address is present."""
        return address in self.history

    @hass_callback
    def async_discovered_service_info(self) -> list[BluetoothServiceInfoBleak]:
        """Return if the address is present."""
        return [
            BluetoothServiceInfoBleak.from_advertisement(
                history.ble_device, history.advertisement_data, SOURCE_LOCAL
            )
            for history in self.history.values()
        ]

    @hass_callback
    def async_rediscover_address(self, address: str) -> None:
        """Trigger discovery of devices which have already been seen."""
        self._integration_matcher.async_clear_address(address)

    def async_register_scanner(self, scanner: HaScanner) -> CALLBACK_TYPE:
        """Register a new scanner."""

        def _unregister_scanner() -> None:
            self._scanners.remove(scanner)

        self._scanners.append(scanner)
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
        for history in self.history.values():
            _dispatch_bleak_callback(
                callback, filters, history.ble_device, history.advertisement_data
            )

        return _remove_callback

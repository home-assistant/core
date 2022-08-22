"""The bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable, Iterable
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
    STALE_ADVERTISEMENT_SECONDS,
    UNAVAILABLE_TRACK_SECONDS,
    AdapterDetails,
)
from .match import (
    ADDRESS,
    BluetoothCallbackMatcher,
    IntegrationMatcher,
    ble_device_matches,
)
from .models import (
    AdvertisementHistory,
    BaseHaScanner,
    BluetoothCallback,
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from .usage import install_multiple_bleak_catcher, uninstall_multiple_bleak_catcher
from .util import async_get_bluetooth_adapters

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData


FILTER_UUIDS: Final = "UUIDs"


RSSI_SWITCH_THRESHOLD = 6

_LOGGER = logging.getLogger(__name__)


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
        self._cancel_unavailable_tracking: list[CALLBACK_TYPE] = []

        self._unavailable_callbacks: dict[str, list[Callable[[str], None]]] = {}
        self._connectable_unavailable_callbacks: dict[
            str, list[Callable[[str], None]]
        ] = {}
        self._callbacks: list[
            tuple[BluetoothCallback, BluetoothCallbackMatcher | None]
        ] = []
        self._connectable_callbacks: list[
            tuple[BluetoothCallback, BluetoothCallbackMatcher | None]
        ] = []
        self._bleak_callbacks: list[
            tuple[AdvertisementDataCallback, dict[str, set[str]]]
        ] = []
        self._history: dict[str, AdvertisementHistory] = {}
        self._connectable_history: dict[str, AdvertisementHistory] = {}
        self._scanners: list[BaseHaScanner] = []
        self._connectable_scanners: list[BaseHaScanner] = []
        self._adapters: dict[str, AdapterDetails] = {}

    def _find_adapter_by_address(self, address: str) -> str | None:
        for adapter, details in self._adapters.items():
            if details[ADAPTER_ADDRESS] == address:
                return adapter
        return None

    async def async_get_bluetooth_adapters(
        self, cached: bool = True
    ) -> dict[str, AdapterDetails]:
        """Get bluetooth adapters."""
        if not cached or not self._adapters:
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
            for cancel in self._cancel_unavailable_tracking:
                cancel()
            self._cancel_unavailable_tracking.clear()
        uninstall_multiple_bleak_catcher()

    @hass_callback
    def async_all_discovered_devices(self, connectable: bool) -> Iterable[BLEDevice]:
        """Return all of discovered devices from all the scanners including duplicates."""
        scanners = self._get_scanners_by_type(connectable)
        return itertools.chain.from_iterable(
            scanner.discovered_devices for scanner in scanners
        )

    @hass_callback
    def async_discovered_devices(self, connectable: bool) -> list[BLEDevice]:
        """Return all of combined best path to discovered from all the scanners."""
        all_history = self._get_history_by_type(connectable)
        return [history.ble_device for history in all_history.values()]

    @hass_callback
    def async_setup_unavailable_tracking(self) -> None:
        """Set up the unavailable tracking."""
        self._async_setup_unavailable_tracking(True)
        self._async_setup_unavailable_tracking(False)

    @hass_callback
    def _async_setup_unavailable_tracking(self, connectable: bool) -> None:
        """Set up the unavailable tracking."""

        @hass_callback
        def _async_check_unavailable(now: datetime) -> None:
            """Watch for unavailable devices."""
            history = self._get_history_by_type(connectable)
            history_set = set(history)
            active_addresses = {
                device.address
                for device in self.async_all_discovered_devices(connectable)
            }
            disappeared = history_set.difference(active_addresses)
            unavailable_callbacks = self._get_unavailable_callbacks_by_type(connectable)
            for address in disappeared:
                del history[address]
                if not (callbacks := unavailable_callbacks.get(address)):
                    continue
                for callback in callbacks:
                    try:
                        callback(address)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception("Error in unavailable callback")

        self._cancel_unavailable_tracking.append(
            async_track_time_interval(
                self.hass,
                _async_check_unavailable,
                timedelta(seconds=UNAVAILABLE_TRACK_SECONDS),
            )
        )

    @hass_callback
    def scanner_adv_received(self, new_history: AdvertisementHistory) -> None:
        """Handle a new advertisement from any scanner.

        Callbacks from all the scanners arrive here.

        In the future we will only process callbacks if

        - The device is not in the history
        - The RSSI is above a certain threshold better than
          than the source from the history or the timestamp
          in the history is older than 180s
        """
        device = new_history.ble_device
        connectable = new_history.connectable
        address = device.address
        all_history = self._get_history_by_type(connectable)
        old_history = all_history.get(address)
        if old_history and _prefer_previous_adv(old_history, new_history):
            return

        self._history[address] = new_history
        advertisement_data = new_history.advertisement_data
        source = new_history.source

        if connectable:
            self._connectable_history[address] = new_history
            # Bleak callbacks must get a connectable device

            for callback_filters in self._bleak_callbacks:
                _dispatch_bleak_callback(*callback_filters, device, advertisement_data)

        matched_domains = self._integration_matcher.match_domains(
            device, advertisement_data, connectable
        )
        _LOGGER.debug(
            "%s: %s %s match: %s",
            source,
            address,
            advertisement_data,
            matched_domains,
        )

        if (
            not matched_domains
            and not self._callbacks
            and not self._connectable_callbacks
        ):
            return

        service_info: BluetoothServiceInfoBleak | None = None
        for connectable_callback in (True, False):
            callback_type = self._get_callbacks_by_type(connectable_callback)
            for callback, matcher in callback_type:
                if matcher is None or ble_device_matches(
                    matcher, device, advertisement_data, connectable_callback
                ):
                    if service_info is None:
                        service_info = (
                            BluetoothServiceInfoBleak.from_advertisement_with_source(
                                device, advertisement_data, source, connectable
                            )
                        )
                    try:
                        callback(service_info, BluetoothChange.ADVERTISEMENT)
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception("Error in bluetooth callback")

        if not matched_domains:
            return
        if service_info is None:
            service_info = BluetoothServiceInfoBleak.from_advertisement_with_source(
                device, advertisement_data, source, connectable
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
        self, callback: Callable[[str], None], address: str, connectable: bool
    ) -> Callable[[], None]:
        """Register a callback."""
        unavailable_callbacks = self._get_unavailable_callbacks_by_type(connectable)
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
        connectable: bool,
        matcher: BluetoothCallbackMatcher | None = None,
    ) -> Callable[[], None]:
        """Register a callback."""
        callbacks = self._get_callbacks_by_type(connectable)
        all_history = self._get_history_by_type(connectable)

        callback_entry = (callback, matcher)
        callbacks.append(callback_entry)

        @hass_callback
        def _async_remove_callback() -> None:
            callbacks.remove(callback_entry)

        # If we have history for the subscriber, we can trigger the callback
        # immediately with the last packet so the subscriber can see the
        # device.
        if (
            matcher
            and (address := matcher.get(ADDRESS))
            and (history := all_history.get(address))
        ):
            try:
                callback(
                    BluetoothServiceInfoBleak.from_advertisement_with_source(
                        history.ble_device,
                        history.advertisement_data,
                        history.source,
                        connectable,
                    ),
                    BluetoothChange.ADVERTISEMENT,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error in bluetooth callback")

        return _async_remove_callback

    @hass_callback
    def async_ble_device_from_address(
        self, address: str, connectable: bool
    ) -> BLEDevice | None:
        """Return the BLEDevice if present."""
        all_history = self._get_history_by_type(connectable)
        if history := all_history.get(address):
            return history.ble_device
        return None

    @hass_callback
    def async_address_present(self, address: str, connectable: bool) -> bool:
        """Return if the address is present."""
        return address in self._get_history_by_type(connectable)

    @hass_callback
    def async_discovered_service_info(
        self, connectable: bool
    ) -> list[BluetoothServiceInfoBleak]:
        """Return if the address is present."""
        all_history = self._get_history_by_type(connectable)
        return [
            BluetoothServiceInfoBleak.from_advertisement_with_source(
                history.ble_device,
                history.advertisement_data,
                history.source,
                connectable,
            )
            for history in all_history.values()
        ]

    @hass_callback
    def async_rediscover_address(self, address: str) -> None:
        """Trigger discovery of devices which have already been seen."""
        self._integration_matcher.async_clear_address(address)

    def _get_scanners_by_type(self, connectable: bool) -> list[BaseHaScanner]:
        """Return the scanners by type."""
        return self._connectable_scanners if connectable else self._scanners

    def _get_unavailable_callbacks_by_type(
        self, connectable: bool
    ) -> dict[str, list[Callable[[str], None]]]:
        """Return the unavailable callbacks by type."""
        return (
            self._connectable_unavailable_callbacks
            if connectable
            else self._unavailable_callbacks
        )

    def _get_history_by_type(
        self, connectable: bool
    ) -> dict[str, AdvertisementHistory]:
        """Return the history by type."""
        return self._connectable_history if connectable else self._history

    def _get_callbacks_by_type(
        self, connectable: bool
    ) -> list[tuple[BluetoothCallback, BluetoothCallbackMatcher | None]]:
        """Return the callbacks by type."""
        return self._connectable_callbacks if connectable else self._callbacks

    def async_register_scanner(
        self, scanner: BaseHaScanner, connectable: bool
    ) -> CALLBACK_TYPE:
        """Register a new scanner."""
        scanners = self._get_scanners_by_type(connectable)

        def _unregister_scanner() -> None:
            scanners.remove(scanner)

        scanners.append(scanner)
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
                callback, filters, history.ble_device, history.advertisement_data
            )

        return _remove_callback

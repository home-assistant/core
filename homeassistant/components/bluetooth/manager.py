"""The bluetooth integration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial
import itertools
import logging

from bleak_retry_connector import BleakSlotManager
from bluetooth_adapters import BluetoothAdapters
from habluetooth import BaseHaRemoteScanner, BaseHaScanner, BluetoothManager

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_LOGGING_CHANGED
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.helpers import discovery_flow

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
from .util import async_load_history_from_system

_LOGGER = logging.getLogger(__name__)


class HomeAssistantBluetoothManager(BluetoothManager):
    """Manage Bluetooth for Home Assistant."""

    __slots__ = (
        "hass",
        "storage",
        "_integration_matcher",
        "_callback_index",
        "_cancel_logging_listener",
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
        self.storage = storage
        self._integration_matcher = integration_matcher
        self._callback_index = BluetoothCallbackMatcherIndex()
        self._cancel_logging_listener: CALLBACK_TYPE | None = None
        super().__init__(bluetooth_adapters, slot_manager)
        self._async_logging_changed()

    @hass_callback
    def _async_logging_changed(self, event: Event | None = None) -> None:
        """Handle logging change."""
        self._debug = _LOGGER.isEnabledFor(logging.DEBUG)

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

    def _discover_service_info(self, service_info: BluetoothServiceInfoBleak) -> None:
        matched_domains = self._integration_matcher.match_domains(service_info)
        if self._debug:
            _LOGGER.debug(
                "%s: %s match: %s",
                self._async_describe_source(service_info),
                service_info,
                matched_domains,
            )

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

    def _address_disappeared(self, address: str) -> None:
        """Dismiss all discoveries for the given address."""
        self._integration_matcher.async_clear_address(address)
        for flow in self.hass.config_entries.flow.async_progress_by_init_data_type(
            BluetoothServiceInfoBleak,
            lambda service_info: bool(service_info.address == address),
        ):
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

    async def async_setup(self) -> None:
        """Set up the bluetooth manager."""
        await super().async_setup()
        self._all_history, self._connectable_history = async_load_history_from_system(
            self._bluetooth_adapters, self.storage
        )
        self._cancel_logging_listener = self.hass.bus.async_listen(
            EVENT_LOGGING_CHANGED, self._async_logging_changed
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        seen: set[str] = set()
        for address, service_info in itertools.chain(
            self._connectable_history.items(), self._all_history.items()
        ):
            if address in seen:
                continue
            seen.add(address)
            self._async_trigger_matching_discovery(service_info)

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
    def async_stop(self, event: Event | None = None) -> None:
        """Stop the Bluetooth integration at shutdown."""
        _LOGGER.debug("Stopping bluetooth manager")
        self._async_save_scanner_histories()
        super().async_stop()
        if self._cancel_logging_listener:
            self._cancel_logging_listener()
            self._cancel_logging_listener = None

    def _async_save_scanner_histories(self) -> None:
        """Save the scanner histories."""
        for scanner in itertools.chain(
            self._connectable_scanners, self._non_connectable_scanners
        ):
            self._async_save_scanner_history(scanner)

    def _async_save_scanner_history(self, scanner: BaseHaScanner) -> None:
        """Save the scanner history."""
        if isinstance(scanner, BaseHaRemoteScanner):
            self.storage.async_set_advertisement_history(
                scanner.source, scanner.serialize_discovered_devices()
            )

    def _async_unregister_scanner(
        self, scanner: BaseHaScanner, unregister: CALLBACK_TYPE
    ) -> None:
        """Unregister a scanner."""
        unregister()
        self._async_save_scanner_history(scanner)

    def async_register_scanner(
        self,
        scanner: BaseHaScanner,
        connection_slots: int | None = None,
    ) -> CALLBACK_TYPE:
        """Register a scanner."""
        if isinstance(scanner, BaseHaRemoteScanner):
            if history := self.storage.async_get_advertisement_history(scanner.source):
                scanner.restore_discovered_devices(history)

        unregister = super().async_register_scanner(scanner, connection_slots)
        return partial(self._async_unregister_scanner, scanner, unregister)

"""The bluetooth integration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial
import itertools
import logging

from bleak_retry_connector import BleakSlotManager
from bluetooth_adapters import (
    ADAPTER_TYPE,
    BluetoothAdapters,
    adapter_human_name,
    adapter_model,
)
from habluetooth import (
    BaseHaRemoteScanner,
    BaseHaScanner,
    BluetoothManager,
    BluetoothScanningMode,
    HaScanner,
)

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_LOGGING_CHANGED
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.helpers import discovery_flow, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.package import is_docker_env

from .const import (
    CONF_SOURCE,
    CONF_SOURCE_CONFIG_ENTRY_ID,
    CONF_SOURCE_DEVICE_ID,
    CONF_SOURCE_DOMAIN,
    CONF_SOURCE_MODEL,
    DOMAIN,
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
from .util import async_load_history_from_system

_LOGGER = logging.getLogger(__name__)


class HomeAssistantBluetoothManager(BluetoothManager):
    """Manage Bluetooth for Home Assistant."""

    __slots__ = (
        "_callback_index",
        "_cancel_logging_listener",
        "_integration_matcher",
        "hass",
        "storage",
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
        discovery_key = discovery_flow.DiscoveryKey(
            domain=DOMAIN,
            key=service_info.address,
            version=1,
        )
        for domain in self._integration_matcher.match_domains(service_info):
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_BLUETOOTH},
                service_info,
                discovery_key=discovery_key,
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

    @hass_callback
    def async_clear_address_from_match_history(self, address: str) -> None:
        """Clear an address from the integration matcher history.

        This allows future advertisements from this address to trigger discovery
        even if the advertisement content has changed but the service data UUIDs
        remain the same.

        Unlike async_rediscover_address, this does not immediately re-trigger
        discovery with the current advertisement in history.
        """
        self._integration_matcher.async_clear_address(address)

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
            except Exception:
                _LOGGER.exception("Error in bluetooth callback")

        if not matched_domains:
            return  # avoid creating DiscoveryKey if there are no matches

        discovery_key = discovery_flow.DiscoveryKey(
            domain=DOMAIN,
            key=service_info.address,
            version=1,
        )
        for domain in matched_domains:
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_BLUETOOTH},
                service_info,
                discovery_key=discovery_key,
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
        async_dispatcher_connect(
            self.hass,
            config_entries.signal_discovered_config_entry_removed(DOMAIN),
            self._handle_config_entry_removed,
        )

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
                except Exception:
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
        self.storage.async_set_advertisement_history(
            scanner.source, scanner.serialize_discovered_devices()
        )

    def _async_unregister_scanner(
        self, scanner: BaseHaScanner, unregister: CALLBACK_TYPE
    ) -> None:
        """Unregister a scanner."""
        unregister()
        self._async_save_scanner_history(scanner)

    @hass_callback
    def async_register_hass_scanner(
        self,
        scanner: BaseHaScanner,
        connection_slots: int | None = None,
        source_domain: str | None = None,
        source_model: str | None = None,
        source_config_entry_id: str | None = None,
        source_device_id: str | None = None,
    ) -> CALLBACK_TYPE:
        """Register a scanner."""
        cancel = self.async_register_scanner(scanner, connection_slots)
        if (
            isinstance(scanner, BaseHaRemoteScanner)
            and source_domain
            and source_config_entry_id
        ):
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                    data={
                        CONF_SOURCE: scanner.source,
                        CONF_SOURCE_DOMAIN: source_domain,
                        CONF_SOURCE_MODEL: source_model,
                        CONF_SOURCE_CONFIG_ENTRY_ID: source_config_entry_id,
                        CONF_SOURCE_DEVICE_ID: source_device_id,
                    },
                )
            )
        return cancel

    def async_register_scanner(
        self,
        scanner: BaseHaScanner,
        connection_slots: int | None = None,
    ) -> CALLBACK_TYPE:
        """Register a scanner."""
        if history := self.storage.async_get_advertisement_history(scanner.source):
            scanner.restore_discovered_devices(history)

        unregister = super().async_register_scanner(scanner, connection_slots)
        return partial(self._async_unregister_scanner, scanner, unregister)

    @hass_callback
    def async_remove_scanner(self, source: str) -> None:
        """Remove a scanner."""
        self.storage.async_remove_advertisement_history(source)
        if entry := self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, source
        ):
            self.hass.async_create_task(
                self.hass.config_entries.async_remove(entry.entry_id),
                f"Removing {source} Bluetooth config entry",
            )

    @hass_callback
    def _handle_config_entry_removed(
        self,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Handle config entry changes."""
        for discovery_key in entry.discovery_keys[DOMAIN]:
            if discovery_key.version != 1 or not isinstance(discovery_key.key, str):
                continue
            address = discovery_key.key
            _LOGGER.debug("Rediscover address %s", address)
            self.async_rediscover_address(address)

    def on_scanner_start(self, scanner: BaseHaScanner) -> None:
        """Handle when a scanner starts.

        Create or delete repair issues for local adapters based on degraded mode.
        """
        super().on_scanner_start(scanner)

        # Only handle repair issues for local adapters (HaScanner instances)
        if not isinstance(scanner, HaScanner):
            return
        self.async_check_degraded_mode(scanner)
        self.async_check_scanning_mode(scanner)

    @hass_callback
    def async_check_scanning_mode(self, scanner: HaScanner) -> None:
        """Check if the scanner is running in passive mode when active mode is requested."""
        passive_mode_issue_id = f"bluetooth_adapter_passive_mode_{scanner.source}"

        # Check if scanner is NOT in passive mode when active mode was requested
        if not (
            scanner.requested_mode is BluetoothScanningMode.ACTIVE
            and scanner.current_mode is BluetoothScanningMode.PASSIVE
        ):
            # Delete passive mode issue if it exists and we're not in passive fallback
            ir.async_delete_issue(self.hass, DOMAIN, passive_mode_issue_id)
            return

        # Create repair issue for passive mode fallback
        adapter_name = adapter_human_name(
            scanner.adapter, scanner.mac_address or "00:00:00:00:00:00"
        )
        adapter_details = self._bluetooth_adapters.adapters.get(scanner.adapter)
        model = adapter_model(adapter_details) if adapter_details else None

        # Determine adapter type for specific instructions
        # Default to USB for any other type or unknown
        if adapter_details and adapter_details.get(ADAPTER_TYPE) == "uart":
            translation_key = "bluetooth_adapter_passive_mode_uart"
        else:
            translation_key = "bluetooth_adapter_passive_mode_usb"

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            passive_mode_issue_id,
            is_fixable=False,  # Requires a reboot or unplug
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders={
                "adapter": adapter_name,
                "model": model or "Unknown",
            },
        )

    @hass_callback
    def async_check_degraded_mode(self, scanner: HaScanner) -> None:
        """Check if we are in degraded mode and create/delete repair issues."""
        issue_id = f"bluetooth_adapter_missing_permissions_{scanner.source}"

        # Delete any existing issue if not in degraded mode
        if not self.is_operating_degraded():
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return

        # Only create repair issues for Docker-based installations where users
        # can fix permissions. This includes: Home Assistant Supervised,
        # Home Assistant Container, and third-party containers
        if not is_docker_env():
            return

        # Create repair issue for degraded mode in Docker (including Supervised)
        adapter_name = adapter_human_name(
            scanner.adapter, scanner.mac_address or "00:00:00:00:00:00"
        )

        # Try to get adapter details from the bluetooth adapters
        adapter_details = self._bluetooth_adapters.adapters.get(scanner.adapter)
        model = adapter_model(adapter_details) if adapter_details else None

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,  # Not fixable from within HA - requires
            # container restart with new permissions
            severity=ir.IssueSeverity.WARNING,
            translation_key="bluetooth_adapter_missing_permissions",
            translation_placeholders={
                "adapter": adapter_name,
                "model": model or "Unknown",
                "docs_url": "https://www.home-assistant.io/integrations/bluetooth/#additional-details-for-container",
            },
        )

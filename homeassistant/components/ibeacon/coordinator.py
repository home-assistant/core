"""Tracking for iBeacon devices."""
from __future__ import annotations

from ibeacon_ble import (
    APPLE_MFR_ID,
    IBEACON_FIRST_BYTE,
    IBEACON_SECOND_BYTE,
    is_ibeacon_service_info,
    parse,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_IGNORE_ADDRESSES,
    CONF_IGNORE_GROUP_IDS,
    CONF_MIN_RSSI,
    DEFAULT_MIN_RSSI,
    DOMAIN,
    MAX_IDS,
    SIGNAL_IBEACON_DEVICE_NEW,
    SIGNAL_IBEACON_DEVICE_SEEN,
    SIGNAL_IBEACON_DEVICE_UNAVAILABLE,
)

PRIMARY_ENTITY_DOMAIN = "device_tracker"


def signal_unavailable(unique_id: str) -> str:
    """Signal for the unique_id going unavailable."""
    return f"{SIGNAL_IBEACON_DEVICE_UNAVAILABLE}_{unique_id}"


def signal_seen(unique_id: str) -> str:
    """Signal for the unique_id being seen."""
    return f"{SIGNAL_IBEACON_DEVICE_SEEN}_{unique_id}"


class IBeaconCoordinator:
    """Set up the iBeacon Coordinator."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, registry: DeviceRegistry
    ) -> None:
        """Initialize the Coordinator."""
        self.hass = hass
        self._entry = entry
        self._min_rssi = entry.options.get(CONF_MIN_RSSI) or DEFAULT_MIN_RSSI

        self._unique_ids: set[str] = set()

        self._group_ids_by_address: dict[str, set[str]] = {}
        self._unique_ids_by_address: dict[str, set[str]] = {}
        self._unique_ids_by_group_id: dict[str, set[str]] = {}
        self._addresses_by_group_id: dict[str, set[str]] = {}

        self._unavailable_trackers: dict[str, CALLBACK_TYPE] = {}
        self._dev_reg = registry

        self._ignore_addresses: set[str] = set(
            entry.data.get(CONF_IGNORE_ADDRESSES, [])
        )
        self._ignore_group_ids: set[str] = set(
            entry.data.get(CONF_IGNORE_GROUP_IDS, [])
        )

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle unavailable devices."""
        address = service_info.address
        self._async_cancel_unavailable_tracker(address)
        for unique_id in self._unique_ids_by_address[address]:
            async_dispatcher_send(self.hass, signal_unavailable(unique_id))

    @callback
    def _async_cancel_unavailable_tracker(self, address: str) -> None:
        """Cancel unavailable tracking for an address."""
        self._unavailable_trackers.pop(address)()

    @callback
    def _async_ignore_address(self, address: str) -> None:
        """Ignore an address that does not follow the spec and any entities created by it."""
        self._ignore_addresses.add(address)
        self._async_cancel_unavailable_tracker(address)
        self.hass.config_entries.async_update_entry(
            self._entry,
            data=self._entry.data
            | {CONF_IGNORE_ADDRESSES: sorted(self._ignore_addresses)},
        )
        self._async_purge_untrackable_entities(self._unique_ids_by_address[address])
        self._group_ids_by_address.pop(address)
        self._unique_ids_by_address.pop(address)

    @callback
    def _async_purge_untrackable_entities(self, unique_ids: set[str]) -> None:
        """Remove entities that are no longer trackable."""
        for unique_id in unique_ids:
            if device := self._dev_reg.async_get_device({(DOMAIN, unique_id)}):
                self._dev_reg.async_remove_device(device.id)
            self._unique_ids.discard(unique_id)

    @callback
    def _async_ignore_group(self, group_id: str) -> None:
        """Ignore a group that is using rotating mac addresses since its untrackable."""
        self._ignore_group_ids.add(group_id)
        self.hass.config_entries.async_update_entry(
            self._entry,
            data=self._entry.data
            | {CONF_IGNORE_GROUP_IDS: sorted(self._ignore_group_ids)},
        )
        self._async_purge_untrackable_entities(self._unique_ids_by_group_id[group_id])
        self._unique_ids_by_group_id.pop(group_id)
        self._addresses_by_group_id.pop(group_id)

    def _async_track_ibeacon(self, address: str, group_id: str, unique_id: str) -> None:
        """Track an iBeacon."""
        self._unique_ids_by_address.setdefault(address, set()).add(unique_id)
        self._group_ids_by_address.setdefault(address, set()).add(group_id)

        self._unique_ids_by_group_id.setdefault(group_id, set()).add(unique_id)
        self._addresses_by_group_id.setdefault(group_id, set()).add(address)

    @callback
    def _async_update_ibeacon(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a bluetooth callback."""
        if service_info.address in self._ignore_addresses:
            return
        if service_info.rssi < self._min_rssi:
            return
        if not (parsed := parse(service_info)):
            return
        uuid_str = str(parsed.uuid)
        group_id = f"{uuid_str}_{parsed.major}_{parsed.minor}"
        if group_id in self._ignore_group_ids:
            return
        address = service_info.address
        unique_id = f"{group_id}_{address}"
        new = unique_id not in self._unique_ids
        self._unique_ids.add(unique_id)
        self._async_track_ibeacon(address, group_id, unique_id)

        if address not in self._unavailable_trackers:
            self._unavailable_trackers[address] = bluetooth.async_track_unavailable(
                self.hass, self._async_handle_unavailable, address
            )

        # Some manufacturers violate the spec and flood us with random
        # data (sometimes its temperature data).
        #
        # Once we see more than MAX_IDS from the same
        # address we remove all the trackers for that address and add the
        # address to the ignore list since we know its garbage data.
        if len(self._group_ids_by_address[address]) >= MAX_IDS:
            self._async_ignore_address(address)
            return

        # Once we see more than MAX_IDS from the same
        # group_id we remove all the trackers for that group_id
        # as it means the addresses are being rotated and they
        # cannot be tracked
        if len(self._addresses_by_group_id[group_id]) >= MAX_IDS:
            self._async_ignore_group(group_id)
            return

        if new:
            if service_info.address in (
                service_info.name,
                service_info.name.replace("_", ":"),
            ):
                identifier = f"{parsed.uuid} {parsed.major}.{parsed.minor}"
            else:
                identifier = service_info.name
            async_dispatcher_send(
                self.hass,
                SIGNAL_IBEACON_DEVICE_NEW,
                unique_id,
                identifier,
                parsed,
            )
            return
        async_dispatcher_send(
            self.hass,
            signal_seen(unique_id),
            parsed,
        )

    @callback
    def _async_stop(self) -> None:
        """Stop the Coordinator."""
        for cancel in self._unavailable_trackers.values():
            cancel()
        self._unavailable_trackers.clear()

    async def _entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        self._min_rssi = entry.options.get(CONF_MIN_RSSI) or DEFAULT_MIN_RSSI

    @callback
    def _async_restore_from_registry(self) -> None:
        """Restore the state of the Coordinator from the entity registry."""
        for device in self._dev_reg.devices.values():
            unique_id = None
            for identifier in device.identifiers:
                if identifier[0] == DOMAIN:
                    unique_id = identifier[1]
                    break
            if not unique_id:
                continue
            if unique_id.count("_") != 3:
                continue
            uuid, major, minor, address = unique_id.split("_")
            group_id = f"{uuid}_{major}_{minor}"
            self._async_track_ibeacon(address, group_id, unique_id)

    @callback
    def async_start(self) -> None:
        """Start the Coordinator."""
        self._async_restore_from_registry()
        self._entry.async_on_unload(
            self._entry.add_update_listener(self._entry_updated)
        )
        self._entry.async_on_unload(
            bluetooth.async_register_callback(
                self.hass,
                self._async_update_ibeacon,
                BluetoothCallbackMatcher(
                    connectable=False,
                    manufacturer_id=APPLE_MFR_ID,
                    manufacturer_data_start=[IBEACON_FIRST_BYTE, IBEACON_SECOND_BYTE],
                ),  # We will take data from any source
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        )
        self._entry.async_on_unload(self._async_stop)
        # Replay any that are already there.
        for service_info in bluetooth.async_discovered_service_info(
            self.hass, connectable=False
        ):
            if is_ibeacon_service_info(service_info):
                self._async_update_ibeacon(
                    service_info, bluetooth.BluetoothChange.ADVERTISEMENT
                )

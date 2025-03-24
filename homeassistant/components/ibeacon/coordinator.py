"""Tracking for iBeacon devices."""

from __future__ import annotations

from datetime import datetime
import logging
import time

from ibeacon_ble import (
    APPLE_MFR_ID,
    IBEACON_FIRST_BYTE,
    IBEACON_SECOND_BYTE,
    iBeaconAdvertisement,
    iBeaconParser,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_ALLOW_NAMELESS_UUIDS,
    CONF_IGNORE_ADDRESSES,
    CONF_IGNORE_UUIDS,
    DOMAIN,
    MAX_IDS,
    MAX_IDS_PER_UUID,
    MIN_SEEN_TRANSIENT_NEW,
    SIGNAL_IBEACON_DEVICE_NEW,
    SIGNAL_IBEACON_DEVICE_SEEN,
    SIGNAL_IBEACON_DEVICE_UNAVAILABLE,
    UNAVAILABLE_TIMEOUT,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

MONOTONIC_TIME = time.monotonic


def signal_unavailable(unique_id: str) -> str:
    """Signal for the unique_id going unavailable."""
    return f"{SIGNAL_IBEACON_DEVICE_UNAVAILABLE}_{unique_id}"


def signal_seen(unique_id: str) -> str:
    """Signal for the unique_id being seen."""
    return f"{SIGNAL_IBEACON_DEVICE_SEEN}_{unique_id}"


def make_short_address(address: str) -> str:
    """Convert a Bluetooth address to a short address."""
    results = address.replace("-", ":").split(":")
    return f"{results[-2].upper()}{results[-1].upper()}"[-4:]


@callback
def async_name(
    service_info: bluetooth.BluetoothServiceInfoBleak,
    ibeacon_advertisement: iBeaconAdvertisement,
    unique_address: bool = False,
) -> str:
    """Return a name for the device."""
    if service_info.address in (
        service_info.name,
        service_info.name.replace("-", ":"),
    ):
        base_name = f"{ibeacon_advertisement.uuid}_{ibeacon_advertisement.major}_{ibeacon_advertisement.minor}"
    else:
        base_name = service_info.name
    if unique_address:
        short_address = make_short_address(service_info.address)
        if not base_name.upper().endswith(short_address):
            return f"{base_name} {short_address}"
    return base_name


@callback
def _async_dispatch_update(
    hass: HomeAssistant,
    device_id: str,
    service_info: bluetooth.BluetoothServiceInfoBleak,
    ibeacon_advertisement: iBeaconAdvertisement,
    new: bool,
    unique_address: bool,
) -> None:
    """Dispatch an update."""
    if new:
        async_dispatcher_send(
            hass,
            SIGNAL_IBEACON_DEVICE_NEW,
            device_id,
            async_name(service_info, ibeacon_advertisement, unique_address),
            ibeacon_advertisement,
        )
        return

    async_dispatcher_send(
        hass,
        signal_seen(device_id),
        ibeacon_advertisement,
    )


class IBeaconCoordinator:
    """Set up the iBeacon Coordinator."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, registry: DeviceRegistry
    ) -> None:
        """Initialize the Coordinator."""
        self.hass = hass
        self._entry = entry
        self._dev_reg = registry
        self._ibeacon_parser = iBeaconParser()

        # iBeacon devices that do not follow the spec
        # and broadcast custom data in the major and minor fields
        self._ignore_addresses: set[str] = set(
            entry.data.get(CONF_IGNORE_ADDRESSES, [])
        )
        # iBeacon devices that do not follow the spec
        # and broadcast custom data in the major and minor fields
        self._ignore_uuids: set[str] = set(entry.data.get(CONF_IGNORE_UUIDS, []))

        # iBeacons with fixed MAC addresses
        self._last_ibeacon_advertisement_by_unique_id: dict[
            str, iBeaconAdvertisement
        ] = {}
        self._transient_seen_count: dict[str, int] = {}
        self._group_ids_by_address: dict[str, set[str]] = {}
        self._unique_ids_by_address: dict[str, set[str]] = {}
        self._unique_ids_by_group_id: dict[str, set[str]] = {}
        self._addresses_by_group_id: dict[str, set[str]] = {}
        self._unavailable_trackers: dict[str, CALLBACK_TYPE] = {}

        # iBeacon with random MAC addresses
        self._group_ids_random_macs: set[str] = set()
        self._last_seen_by_group_id: dict[str, bluetooth.BluetoothServiceInfoBleak] = {}
        self._unavailable_group_ids: set[str] = set()

        # iBeacons with random MAC addresses, fixed UUID, random major/minor
        self._major_minor_by_uuid: dict[str, set[tuple[int, int]]] = {}

        # iBeacons from devices with no name
        self._allow_nameless_uuids = set(
            entry.options.get(CONF_ALLOW_NAMELESS_UUIDS, [])
        )
        self._ignored_nameless_by_uuid: dict[str, set[str]] = {}

        self._entry.async_on_unload(
            self._entry.add_update_listener(self.async_config_entry_updated)
        )

    @callback
    def async_device_id_seen(self, device_id: str) -> bool:
        """Return True if the device_id has been seen since boot."""
        return bool(
            device_id in self._last_ibeacon_advertisement_by_unique_id
            or device_id in self._last_seen_by_group_id
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
        self._transient_seen_count.pop(address, None)

    @callback
    def _async_ignore_uuid(self, uuid: str) -> None:
        """Ignore an UUID that does not follow the spec and any entities created by it."""
        self._ignore_uuids.add(uuid)
        major_minor_by_uuid = self._major_minor_by_uuid.pop(uuid)
        unique_ids_to_purge = set()
        for major, minor in major_minor_by_uuid:
            group_id = f"{uuid}_{major}_{minor}"
            if unique_ids := self._unique_ids_by_group_id.pop(group_id, None):
                unique_ids_to_purge.update(unique_ids)
            for address in self._addresses_by_group_id.pop(group_id, []):
                self._async_cancel_unavailable_tracker(address)
                self._unique_ids_by_address.pop(address)
                self._group_ids_by_address.pop(address)
        self._async_purge_untrackable_entities(unique_ids_to_purge)
        entry_data = self._entry.data
        new_data = entry_data | {CONF_IGNORE_UUIDS: list(self._ignore_uuids)}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

    @callback
    def _async_ignore_address(self, address: str) -> None:
        """Ignore an address that does not follow the spec and any entities created by it."""
        self._ignore_addresses.add(address)
        self._async_cancel_unavailable_tracker(address)
        entry_data = self._entry.data
        new_data = entry_data | {CONF_IGNORE_ADDRESSES: list(self._ignore_addresses)}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)
        self._async_purge_untrackable_entities(self._unique_ids_by_address[address])
        self._group_ids_by_address.pop(address)
        self._unique_ids_by_address.pop(address)

    @callback
    def _async_purge_untrackable_entities(self, unique_ids: set[str]) -> None:
        """Remove entities that are no longer trackable."""
        for unique_id in unique_ids:
            if device := self._dev_reg.async_get_device(
                identifiers={(DOMAIN, unique_id)}
            ):
                self._dev_reg.async_remove_device(device.id)
            self._last_ibeacon_advertisement_by_unique_id.pop(unique_id, None)

    @callback
    def _async_convert_random_mac_tracking(
        self,
        group_id: str,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Switch to random mac tracking method when a group is using rotating mac addresses."""
        self._group_ids_random_macs.add(group_id)
        self._async_purge_untrackable_entities(self._unique_ids_by_group_id[group_id])
        self._unique_ids_by_group_id.pop(group_id)
        self._addresses_by_group_id.pop(group_id)
        self._async_update_ibeacon_with_random_mac(
            group_id, service_info, ibeacon_advertisement
        )

    def _async_track_ibeacon_with_unique_address(
        self, address: str, group_id: str, unique_id: str
    ) -> None:
        """Track an iBeacon with a unique address."""
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
        if not (ibeacon_advertisement := self._ibeacon_parser.parse(service_info)):
            return

        uuid_str = str(ibeacon_advertisement.uuid)
        if uuid_str in self._ignore_uuids:
            return

        _LOGGER.debug("update beacon %s", uuid_str)

        major = ibeacon_advertisement.major
        minor = ibeacon_advertisement.minor
        major_minor_by_uuid = self._major_minor_by_uuid.setdefault(uuid_str, set())
        if len(major_minor_by_uuid) + 1 > MAX_IDS_PER_UUID:
            self._async_ignore_uuid(uuid_str)
            return

        major_minor_by_uuid.add((major, minor))
        group_id = f"{uuid_str}_{major}_{minor}"

        if group_id in self._group_ids_random_macs:
            self._async_update_ibeacon_with_random_mac(
                group_id, service_info, ibeacon_advertisement
            )
            return

        self._async_update_ibeacon_with_unique_address(
            group_id, service_info, ibeacon_advertisement
        )

    @callback
    def _async_update_ibeacon_with_random_mac(
        self,
        group_id: str,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Update iBeacons with random mac addresses."""
        new = group_id not in self._last_seen_by_group_id
        self._last_seen_by_group_id[group_id] = service_info
        self._unavailable_group_ids.discard(group_id)
        _async_dispatch_update(
            self.hass, group_id, service_info, ibeacon_advertisement, new, False
        )

    @callback
    def _async_update_ibeacon_with_unique_address(
        self,
        group_id: str,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        # Handle iBeacon with a fixed mac address
        # and or detect if the iBeacon is using a rotating mac address
        # and switch to random mac tracking method
        address = service_info.address
        unique_id = f"{group_id}_{address}"
        new = unique_id not in self._last_ibeacon_advertisement_by_unique_id
        uuid = str(ibeacon_advertisement.uuid)

        # Reject creating new trackers if the name is not set (unless the uuid is allowlisted).
        if (
            new
            and uuid not in self._allow_nameless_uuids
            and (
                service_info.device.name is None
                or service_info.device.name.replace("-", ":")
                == service_info.device.address
            )
        ):
            # Store the ignored addresses, cause the uuid might be allowlisted later
            self._ignored_nameless_by_uuid.setdefault(uuid, set()).add(address)

            _LOGGER.debug("ignoring new beacon %s due to empty device name", unique_id)
            return

        previously_tracked = address in self._unique_ids_by_address
        self._last_ibeacon_advertisement_by_unique_id[unique_id] = ibeacon_advertisement
        self._async_track_ibeacon_with_unique_address(address, group_id, unique_id)
        if address not in self._unavailable_trackers:
            self._unavailable_trackers[address] = bluetooth.async_track_unavailable(
                self.hass, self._async_handle_unavailable, address
            )

        if not previously_tracked and new and ibeacon_advertisement.transient:
            # Do not create a new tracker right away for transient devices
            # If they keep advertising, we will create entities for them
            # once _async_update_rssi_and_transients has seen them enough times
            self._transient_seen_count[address] = 1
            return

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
        # as it means the addresses are being rotated.
        if len(self._addresses_by_group_id[group_id]) >= MAX_IDS:
            self._async_convert_random_mac_tracking(
                group_id, service_info, ibeacon_advertisement
            )
            return

        _async_dispatch_update(
            self.hass, unique_id, service_info, ibeacon_advertisement, new, True
        )

    @callback
    def _async_stop(self) -> None:
        """Stop the Coordinator."""
        for cancel in self._unavailable_trackers.values():
            cancel()
        self._unavailable_trackers.clear()

    @callback
    def _async_check_unavailable_groups_with_random_macs(self) -> None:
        """Check for random mac groups that have not been seen in a while and mark them as unavailable."""
        now = MONOTONIC_TIME()
        gone_unavailable = [
            group_id
            for group_id in self._group_ids_random_macs
            if group_id not in self._unavailable_group_ids
            and (service_info := self._last_seen_by_group_id.get(group_id))
            and (
                # We will not get callbacks for iBeacons with random macs
                # that rotate infrequently since their advertisement data
                # does not change as the bluetooth.async_register_callback API
                # suppresses callbacks for duplicate advertisements to avoid
                # exposing integrations to the firehose of bluetooth advertisements.
                #
                # To solve this we need to ask for the latest service info for
                # the address we last saw to get the latest timestamp.
                #
                # If there is no last service info for the address we know that
                # the device is no longer advertising.
                not (
                    latest_service_info := bluetooth.async_last_service_info(
                        self.hass, service_info.address, connectable=False
                    )
                )
                or now - latest_service_info.time > UNAVAILABLE_TIMEOUT
            )
        ]
        for group_id in gone_unavailable:
            self._unavailable_group_ids.add(group_id)
            async_dispatcher_send(self.hass, signal_unavailable(group_id))

    @callback
    def _async_update_rssi_and_transients(self) -> None:
        """Check to see if the rssi has changed and update any devices.

        We don't callback on RSSI changes so we need to check them
        here and send them over the dispatcher periodically to
        ensure the distance calculation is update.

        If the transient flag is set we also need to check to see
        if the device is still transmitting and increment the counter
        """
        for (
            unique_id,
            ibeacon_advertisement,
        ) in self._last_ibeacon_advertisement_by_unique_id.items():
            address = unique_id.split("_")[-1]
            service_info = bluetooth.async_last_service_info(
                self.hass, address, connectable=False
            )
            if not service_info:
                continue

            if address in self._transient_seen_count:
                self._transient_seen_count[address] += 1
                if self._transient_seen_count[address] == MIN_SEEN_TRANSIENT_NEW:
                    self._transient_seen_count.pop(address)
                    _async_dispatch_update(
                        self.hass,
                        unique_id,
                        service_info,
                        ibeacon_advertisement,
                        True,
                        True,
                    )
                    continue

            if (
                service_info.rssi != ibeacon_advertisement.rssi
                or service_info.source != ibeacon_advertisement.source
            ):
                ibeacon_advertisement.source = service_info.source
                ibeacon_advertisement.update_rssi(service_info.rssi)
                async_dispatcher_send(
                    self.hass,
                    signal_seen(unique_id),
                    ibeacon_advertisement,
                )

    async def async_config_entry_updated(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Restore ignored nameless beacons when the allowlist is updated."""

        self._allow_nameless_uuids = set(
            self._entry.options.get(CONF_ALLOW_NAMELESS_UUIDS, [])
        )

        for uuid in self._allow_nameless_uuids:
            for address in self._ignored_nameless_by_uuid.pop(uuid, set()):
                _LOGGER.debug(
                    "restoring nameless iBeacon %s from address %s", uuid, address
                )

                if not (
                    service_info := bluetooth.async_last_service_info(
                        self.hass, address, connectable=False
                    )
                ):
                    continue  # no longer available

                # the beacon was ignored, we need to re-process it from scratch
                self._async_update_ibeacon(
                    service_info, bluetooth.BluetoothChange.ADVERTISEMENT
                )

    @callback
    def _async_update(self, _now: datetime) -> None:
        """Update the Coordinator."""
        self._async_check_unavailable_groups_with_random_macs()
        self._async_update_rssi_and_transients()

    @callback
    def _async_restore_from_registry(self) -> None:
        """Restore the state of the Coordinator from the device registry."""
        for device in self._dev_reg.devices.get_devices_for_config_entry_id(
            self._entry.entry_id
        ):
            if not (identifier := next(iter(device.identifiers), None)):
                continue
            unique_id = identifier[1]
            # iBeacons with a fixed MAC address
            if unique_id.count("_") == 3:
                uuid, major, minor, address = unique_id.split("_")
                group_id = f"{uuid}_{major}_{minor}"
                self._async_track_ibeacon_with_unique_address(
                    address, group_id, unique_id
                )
            # iBeacons with a random MAC address
            elif unique_id.count("_") == 2:
                uuid, major, minor = unique_id.split("_")
                group_id = f"{uuid}_{major}_{minor}"
                self._group_ids_random_macs.add(group_id)

    async def async_start(self) -> None:
        """Start the Coordinator."""
        await self._ibeacon_parser.async_setup()
        self._async_restore_from_registry()
        entry = self._entry
        entry.async_on_unload(
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
        entry.async_on_unload(self._async_stop)
        entry.async_on_unload(
            async_track_time_interval(self.hass, self._async_update, UPDATE_INTERVAL)
        )

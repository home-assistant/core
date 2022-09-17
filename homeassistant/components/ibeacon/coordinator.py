"""Tracking for iBeacon devices."""
from __future__ import annotations

from typing import cast

from ibeacon_ble import parse

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_get

from .const import (
    APPLE_MFR_ID,
    CONF_IGNORE_ADDRESSES,
    CONF_MIN_RSSI,
    DEFAULT_MIN_RSSI,
    DOMAIN,
    IBEACON_FIRST_BYTE,
    IBEACON_SECOND_BYTE,
    MAX_UNIQUE_IDS_PER_ADDRESS,
    SIGNAL_IBEACON_DEVICE_NEW,
    SIGNAL_IBEACON_DEVICE_SEEN,
    SIGNAL_IBEACON_DEVICE_UNAVAILABLE,
)


def signal_unavailable(unique_id: str) -> str:
    """Signal for the unique_id going unavailable."""
    return f"{SIGNAL_IBEACON_DEVICE_UNAVAILABLE}_{unique_id}"


def signal_seen(unique_id: str) -> str:
    """Signal for the unique_id being seen."""
    return f"{SIGNAL_IBEACON_DEVICE_SEEN}_{unique_id}"


class IBeaconCoordinator:
    """Set up the iBeacon Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Coordinator."""
        self.hass = hass
        self._entry = entry
        self._min_rssi = entry.options.get(CONF_MIN_RSSI) or DEFAULT_MIN_RSSI
        self._unique_id_power: dict[str, dict[str, int]] = {}
        self._unique_id_source: dict[str, dict[str, str]] = {}
        self._unique_id_distance: dict[str, dict[str, float]] = {}
        self._unique_id_unavailable: dict[str, dict[str, CALLBACK_TYPE]] = {}
        self._address_to_unique_id: dict[str, set[str]] = {}
        self._ignore_addresses: set[str] = set(
            entry.data.get(CONF_IGNORE_ADDRESSES, [])
        )

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle unavailable devices."""
        address = service_info.address
        unique_ids = self._address_to_unique_id.pop(service_info.address)
        for unique_id in unique_ids:
            if self._async_remove_address(unique_id, address):
                async_dispatcher_send(self.hass, signal_unavailable(unique_id))

    @callback
    def _async_remove_address(self, unique_id: str, address: str) -> bool:
        """Remove an address that has gone unavailable.

        Returns True if the unique_id is now unavailable.
        Returns False it the unique_id is still available.
        """
        address_callbacks = self._unique_id_unavailable[unique_id]
        # Cancel the unavailable tracker
        address_callbacks.pop(address)()
        # Remove the power
        self._unique_id_power[unique_id].pop(address)
        self._unique_id_source[unique_id].pop(address)
        self._unique_id_distance[unique_id].pop(address)

        # If its the last beacon broadcasting that unique_id, its now unavailable
        return not bool(address_callbacks)

    @callback
    def _async_ignore_address(self, address: str) -> None:
        """Ignore an address that does not follow the spec and any entities created by it."""
        self._ignore_addresses.add(address)
        unique_ids = self._address_to_unique_id.pop(address)
        self.hass.config_entries.async_update_entry(
            self._entry,
            data=self._entry.data
            | {CONF_IGNORE_ADDRESSES: sorted(self._ignore_addresses)},
        )
        ent_reg = async_get(self.hass)
        for unique_id in unique_ids:
            if self._async_remove_address(unique_id, address) and (
                entry := ent_reg.async_get_entity_id(
                    "device_tracker", DOMAIN, unique_id
                )
            ):
                ent_reg.async_remove(entry)

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
        address = service_info.address
        unique_id = f"{parsed.uuid}_{parsed.major}_{parsed.minor}"
        new = False
        if unique_id not in self._unique_id_unavailable:
            self._unique_id_unavailable[unique_id] = {}
            self._unique_id_power[unique_id] = {}
            self._unique_id_source[unique_id] = {}
            self._unique_id_distance[unique_id] = {}
            new = True
        unavailable_trackers = self._unique_id_unavailable[unique_id]
        power_by_address = self._unique_id_power[unique_id]
        source_by_address = self._unique_id_source[unique_id]
        distance_by_address = self._unique_id_distance[unique_id]
        if address not in unavailable_trackers:
            self._address_to_unique_id.setdefault(address, set()).add(unique_id)
            unavailable_trackers[address] = bluetooth.async_track_unavailable(
                self.hass, self._async_handle_unavailable, address
            )

        power_by_address[address] = parsed.power
        source_by_address[address] = parsed.source
        distance_by_address[address] = calculate_distance(parsed.power, parsed.rssi)

        # Some manufacturers violate the spec and flood us with random
        # data. Once we see more than MAX_UNIQUE_IDS_PER_ADDRESS unique ids
        # from the same address we remove all the trackers for that address
        # and add the address to the ignore list since we know its garbage data.
        if len(self._address_to_unique_id[address]) >= MAX_UNIQUE_IDS_PER_ADDRESS:
            self._async_ignore_address(address)
            return

        rssi_by_address: dict[str, int] = {}
        for address in unavailable_trackers:
            device = bluetooth.async_ble_device_from_address(self.hass, address)
            rssi_by_address[address] = device.rssi if device else None

        if new:
            async_dispatcher_send(
                self.hass,
                SIGNAL_IBEACON_DEVICE_NEW,
                unique_id,
                service_info.name,
                parsed,
                rssi_by_address,
                power_by_address,
                source_by_address,
                distance_by_address,
            )
            return
        async_dispatcher_send(
            self.hass,
            signal_seen(unique_id),
            parsed,
            rssi_by_address,
            power_by_address,
            source_by_address,
            distance_by_address,
        )

    @callback
    def _async_stop(self) -> None:
        """Stop the Coordinator."""
        for address_cancels in self._unique_id_unavailable.values():
            for cancel in address_cancels.values():
                cancel()
        self._unique_id_unavailable.clear()

    async def _entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        self._min_rssi = entry.options.get(CONF_MIN_RSSI) or DEFAULT_MIN_RSSI

    @callback
    def async_start(self) -> None:
        """Start the Coordinator."""
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
        for service_info in bluetooth.async_discovered_service_info(self.hass):
            if (
                (apple_adv := service_info.manufacturer_data.get(APPLE_MFR_ID))
                and len(apple_adv) > 2
                and apple_adv[0] == IBEACON_FIRST_BYTE
                and apple_adv[1] == IBEACON_SECOND_BYTE
            ):
                self._async_update_ibeacon(
                    service_info, bluetooth.BluetoothChange.ADVERTISEMENT
                )


def calculate_distance(power: int, rssi: int) -> float:
    """Calculate the distance between the device and the beacon."""
    if rssi == 0:
        return -1.0
    if (ratio := rssi * 1.0 / power) < 1.0:
        return pow(ratio, 10)
    return cast(float, 0.89976 * pow(ratio, 7.7095) + 0.111)

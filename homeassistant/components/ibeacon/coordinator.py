"""Tracking for iBeacon devices."""
from __future__ import annotations

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
        self._update_cancel: CALLBACK_TYPE | None = None
        self._unique_id_power: dict[str, dict[str, int]] = {}
        self._unique_id_unavailable: dict[str, dict[str, CALLBACK_TYPE]] = {}
        self._address_to_unique_id: dict[str, set[str]] = {}
        self._ignore_addresses: set[str] = set(entry.data[CONF_IGNORE_ADDRESSES])

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle unavailable devices."""
        address = service_info.address
        unique_ids = self._address_to_unique_id.pop(service_info.address)
        for unique_id in unique_ids:
            address_callbacks = self._unique_id_unavailable[unique_id]
            # Cancel the unavailable tracker
            address_callbacks.pop(address)()
            # Remove the power
            self._unique_id_power[unique_id].pop(address)
            # If its the last beacon broadcasting that unique_id, its now unavailable
            if not address_callbacks:
                async_dispatcher_send(self.hass, signal_unavailable(unique_id))

    @callback
    def _async_remove_address(self, address: str) -> None:
        """Remove an address that does not follow the spec and any entities created by it."""
        self._ignore_addresses.add(address)
        unique_ids = self._address_to_unique_id.pop(address)
        self.hass.config_entries.async_update_entry(
            self._entry,
            data=self._entry.data
            | {CONF_IGNORE_ADDRESSES: sorted(self._ignore_addresses)},
        )
        ent_reg = async_get(self.hass)
        for unique_id in unique_ids:
            address_callbacks = self._unique_id_unavailable[unique_id]
            # Cancel the unavailable tracker
            address_callbacks.pop(address)()
            # Remove the power
            self._unique_id_power[unique_id].pop(address, None)
            if not address_callbacks and (
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
        if not (parsed := parse(service_info)):
            return
        address = service_info.address
        uuid = parsed.uuid
        major = parsed.major
        minor = parsed.minor
        unique_id = f"{uuid}_{major}_{minor}"
        new = False
        if unique_id not in self._unique_id_unavailable:
            self._unique_id_unavailable[unique_id] = {}
            self._unique_id_power[unique_id] = {}
            new = True
        unavailable_trackers = self._unique_id_unavailable[unique_id]
        power_by_address = self._unique_id_power[unique_id]
        if address not in unavailable_trackers:
            self._address_to_unique_id.setdefault(address, set()).add(unique_id)
            unavailable_trackers[address] = bluetooth.async_track_unavailable(
                self.hass, self._async_handle_unavailable, address
            )

        # Some manufacturers violate the spec and flood us with random
        # data. Once we see more than 3 unique ids from the same address
        # we remove all the trackers for that address since we know
        # its garbage data.
        if len(self._address_to_unique_id[address]) >= MAX_UNIQUE_IDS_PER_ADDRESS:
            self._async_remove_address(address)
            return

        power_by_address[address] = parsed.power
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
            )
        else:
            async_dispatcher_send(
                self.hass,
                signal_seen(unique_id),
                parsed,
                rssi_by_address,
                power_by_address,
            )

    @callback
    def async_stop(self) -> None:
        """Stop the Coordinator."""
        if self._update_cancel:
            self._update_cancel()
            self._update_cancel = None
        for address_cancels in self._unique_id_unavailable.values():
            for cancel in address_cancels.values():
                cancel()
        self._unique_id_unavailable.clear()

    @callback
    def async_start(self) -> None:
        """Start the Coordinator."""
        self._update_cancel = bluetooth.async_register_callback(
            self.hass,
            self._async_update_ibeacon,
            BluetoothCallbackMatcher(
                connectable=False,
                manufacturer_id=APPLE_MFR_ID,
                manufacturer_data_start=[IBEACON_FIRST_BYTE, IBEACON_SECOND_BYTE],
            ),  # We will take data from any source
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
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

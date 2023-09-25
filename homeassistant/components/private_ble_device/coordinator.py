"""Central manager for tracking devices with random but resolvable MAC addresses."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import cast

from bluetooth_data_tools import get_cipher_for_irk, resolve_private_address
from cryptography.hazmat.primitives.ciphers import Cipher

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UnavailableCallback = Callable[[bluetooth.BluetoothServiceInfoBleak], None]
Cancellable = Callable[[], None]


def async_last_service_info(
    hass: HomeAssistant, irk: bytes
) -> bluetooth.BluetoothServiceInfoBleak | None:
    """Find a BluetoothServiceInfoBleak for the irk.

    This iterates over all currently visible mac addresses and checks them against `irk`.
    It returns the newest.
    """

    # This can't use existing data collected by the coordinator - its called when
    # the coordinator doesn't know about the IRK, so doesn't optimise this lookup.

    cur: bluetooth.BluetoothServiceInfoBleak | None = None
    cipher = get_cipher_for_irk(irk)

    for service_info in bluetooth.async_discovered_service_info(hass, False):
        if resolve_private_address(cipher, service_info.address):
            if not cur or cur.time < service_info.time:
                cur = service_info

    return cur


class PrivateDevicesCoordinator:
    """Monitor private bluetooth devices and correlate them with known IRK.

    This class should not be instanced directly - use `async_get_coordinator` to get an instance.

    There is a single shared coordinator for all instances of this integration. This is to avoid
    unnecessary hashing (AES) operations as much as possible.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self.hass = hass

        self._irks: dict[bytes, Cipher] = {}
        self._unavailable_callbacks: dict[bytes, list[UnavailableCallback]] = {}
        self._service_info_callbacks: dict[
            bytes, list[bluetooth.BluetoothCallback]
        ] = {}

        self._mac_to_irk: dict[str, bytes] = {}
        self._irk_to_mac: dict[bytes, str] = {}

        # These MAC addresses have been compared to the IRK list
        # They are unknown, so we can ignore them.
        self._ignored: dict[str, Cancellable] = {}

        self._unavailability_trackers: dict[bytes, Cancellable] = {}
        self._listener_cancel: Cancellable | None = None

    def _async_ensure_started(self) -> None:
        if not self._listener_cancel:
            self._listener_cancel = bluetooth.async_register_callback(
                self.hass,
                self._async_track_service_info,
                BluetoothCallbackMatcher(connectable=False),
                bluetooth.BluetoothScanningMode.ACTIVE,
            )

    def _async_ensure_stopped(self) -> None:
        if self._listener_cancel:
            self._listener_cancel()
            self._listener_cancel = None

        for cancel in self._ignored.values():
            cancel()
        self._ignored.clear()

    def _async_track_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        # This should be called when the current MAC address associated with an IRK goes away.
        if resolved := self._mac_to_irk.get(service_info.address):
            if callbacks := self._unavailable_callbacks.get(resolved):
                for cb in callbacks:
                    cb(service_info)
            return

    def _async_irk_resolved_to_mac(self, irk: bytes, mac: str) -> None:
        if previous_mac := self._irk_to_mac.get(irk):
            previous_interval = bluetooth.async_get_learned_advertising_interval(
                self.hass, previous_mac
            ) or bluetooth.async_get_fallback_availability_interval(
                self.hass, previous_mac
            )
            if previous_interval:
                bluetooth.async_set_fallback_availability_interval(
                    self.hass, mac, previous_interval
                )

            self._mac_to_irk.pop(previous_mac, None)

        self._mac_to_irk[mac] = irk
        self._irk_to_mac[irk] = mac

        # Stop ignoring this MAC
        self._ignored.pop(mac, None)

        # Ignore availability events for the previous address
        if cancel := self._unavailability_trackers.pop(irk, None):
            cancel()

        # Track available for new address
        self._unavailability_trackers[irk] = bluetooth.async_track_unavailable(
            self.hass, self._async_track_unavailable, mac, False
        )

    def _async_track_service_info(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        mac = service_info.address

        if mac in self._ignored:
            return

        if resolved := self._mac_to_irk.get(mac):
            if callbacks := self._service_info_callbacks.get(resolved):
                for cb in callbacks:
                    cb(service_info, change)
            return

        for irk, cipher in self._irks.items():
            if resolve_private_address(cipher, service_info.address):
                self._async_irk_resolved_to_mac(irk, mac)
                if callbacks := self._service_info_callbacks.get(irk):
                    for cb in callbacks:
                        cb(service_info, change)
                return

        def _unignore(service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
            self._ignored.pop(service_info.address, None)

        self._ignored[mac] = bluetooth.async_track_unavailable(
            self.hass, _unignore, mac, False
        )

    def _async_maybe_learn_irk(self, irk: bytes) -> None:
        """Add irk to list of irks that we can use to resolve RPAs."""
        if irk not in self._irks:
            if service_info := async_last_service_info(self.hass, irk):
                self._async_irk_resolved_to_mac(irk, service_info.address)
            self._irks[irk] = get_cipher_for_irk(irk)

    def _async_maybe_forget_irk(self, irk: bytes) -> None:
        """If no downstream caller is tracking this irk, lets forget it."""
        if irk in self._service_info_callbacks or irk in self._unavailable_callbacks:
            return

        # Ignore availability events for this irk as no
        # one is listening.
        if cancel := self._unavailability_trackers.pop(irk, None):
            cancel()

        del self._irks[irk]

        if mac := self._irk_to_mac.pop(irk, None):
            self._mac_to_irk.pop(mac, None)

        if not self._mac_to_irk:
            self._async_ensure_stopped()

    def async_track_service_info(
        self, callback: bluetooth.BluetoothCallback, irk: bytes
    ) -> Cancellable:
        """Receive a callback when a new advertisement is received for an irk.

        Returns a callback that can be used to cancel the registration.
        """
        self._async_ensure_started()
        self._async_maybe_learn_irk(irk)

        callbacks = self._service_info_callbacks.setdefault(irk, [])
        callbacks.append(callback)

        def _unsubscribe() -> None:
            callbacks.remove(callback)
            if not callbacks:
                self._service_info_callbacks.pop(irk, None)
            self._async_maybe_forget_irk(irk)

        return _unsubscribe

    def async_track_unavailable(
        self,
        callback: UnavailableCallback,
        irk: bytes,
    ) -> Cancellable:
        """Register to receive a callback when an irk is unavailable.

        Returns a callback that can be used to cancel the registration.
        """
        self._async_ensure_started()
        self._async_maybe_learn_irk(irk)

        callbacks = self._unavailable_callbacks.setdefault(irk, [])
        callbacks.append(callback)

        def _unsubscribe() -> None:
            callbacks.remove(callback)
            if not callbacks:
                self._unavailable_callbacks.pop(irk, None)

            self._async_maybe_forget_irk(irk)

        return _unsubscribe


def async_get_coordinator(hass: HomeAssistant) -> PrivateDevicesCoordinator:
    """Create or return an existing PrivateDeviceManager.

    There should only be one per HomeAssistant instance. Associating private
    mac addresses with an IRK involves AES operations. We don't want to
    duplicate that work.
    """
    if existing := hass.data.get(DOMAIN):
        return cast(PrivateDevicesCoordinator, existing)

    pdm = hass.data[DOMAIN] = PrivateDevicesCoordinator(hass)

    return pdm

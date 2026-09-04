"""Coordinator for the Spin EV Charger integration."""

import logging
from typing import override

from bleak.backends.device import BLEDevice
from bleak_retry_connector import close_stale_connections_by_address
from habluetooth import HaBleakClientWrapper
from spinev_ble import ChargerStatus, SpinEvCharger, SpinEvError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHARGING_INTERVAL,
    CONF_CONNECTION_MODE,
    DEFAULT_CONNECTION_MODE,
    DOMAIN,
    IDLE_INTERVAL,
    ConnectionMode,
)

_LOGGER = logging.getLogger(__name__)

type SpinEvConfigEntry = ConfigEntry[SpinEvCoordinator]


class SpinEvCoordinator(DataUpdateCoordinator[ChargerStatus]):
    """Poll one charger over Bluetooth.

    The charger accepts a single Bluetooth client at a time, which makes the
    link itself the thing to decide about. Holding it keeps other clients out,
    the phone app included, for as long as the link lasts, which is what an
    owner who does not want the charger reachable from the street wants.
    Giving it back between polls leaves the app usable. The choice is per
    config entry.

    The poll interval also adapts to what the charger is doing: short while a
    vehicle is charging so power stays current, long while idle so a link that
    is handed back leaves the app long uncontested stretches.
    """

    config_entry: SpinEvConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SpinEvConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=CHARGING_INTERVAL,
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self._keep_connected = (
            entry.options.get(CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE)
            == ConnectionMode.PERSISTENT
        )
        self._charger: SpinEvCharger | None = None

    @override
    async def _async_setup(self) -> None:
        """Clear a link left behind by a previous run."""
        await close_stale_connections_by_address(self.address)

    @override
    async def _async_update_data(self) -> ChargerStatus:
        """Read a full status snapshot."""
        charger = await self._async_charger()
        try:
            await charger.async_connect()
            status = await charger.async_get_status()
        except SpinEvError as err:
            await self.async_release()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_read",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            if not self._keep_connected:
                await self.async_release()

        # A suspended session can resume without a command, so it is polled at
        # the charging rate rather than the idle one.
        session_open = status.state is not None and (
            status.state.is_charging or status.state.is_suspended
        )
        self.update_interval = CHARGING_INTERVAL if session_open else IDLE_INTERVAL
        return status

    async def async_release(self) -> None:
        """Drop the link so another client can reach the charger."""
        charger, self._charger = self._charger, None
        if charger is not None:
            await charger.async_disconnect()

    async def _async_charger(self) -> SpinEvCharger:
        """Return a client, rebuilding it against a fresh device if needed."""
        if self._charger is not None:
            if self._charger.is_connected:
                return self._charger
            # A held link the charger dropped leaves a client that will not
            # reconnect, so it is replaced rather than reused.
            await self.async_release()

        self._charger = SpinEvCharger(
            self._async_ble_device(), client_class=HaBleakClientWrapper
        )
        return self._charger

    @callback
    def _async_ble_device(self) -> BLEDevice:
        """Look the charger up in the Bluetooth manager."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={
                    "address": self.address,
                    "reason": bluetooth.async_address_reachability_diagnostics(
                        self.hass, self.address, BluetoothReachabilityIntent.CONNECTION
                    ),
                },
            )
        return ble_device

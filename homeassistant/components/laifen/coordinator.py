"""Coordinator for the Laifen integration."""

from datetime import timedelta
import logging
from typing import override

from laifen_ble import LaifenConnectionError, LaifenToothbrush, UnsupportedStateError

from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BluetoothCallbackMatcher,
    BluetoothCallbackReplay,
    BluetoothChange,
    BluetoothReachabilityIntent,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_address_reachability_diagnostics,
    async_clear_advertisement_history,
    async_last_service_info,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=1)
ADVERTISEMENT_MAX_AGE = 30

type LaifenConfigEntry = ConfigEntry[LaifenCoordinator]


class LaifenCoordinator(DataUpdateCoordinator[None]):
    """Connect to a Laifen toothbrush whenever it is awake.

    The toothbrush advertises the same data whenever it wakes up, so the
    advertisement history is cleared at setup and after every connection to
    hear the next wake-up. Its state is pushed over the connection, except for
    the battery level, which is read every minute while it stays connected on
    its charger.
    """

    config_entry: LaifenConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LaifenConfigEntry,
        toothbrush: LaifenToothbrush,
        device_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
        )
        self.toothbrush = toothbrush
        self.device_id = device_id
        self._connected = False
        self._firmware_version: str | None = None

    @override
    async def _async_setup(self) -> None:
        """Listen to the toothbrush and to its advertisements."""
        self.config_entry.async_on_unload(
            self.toothbrush.register_callback(self._async_handle_toothbrush_update)
        )
        self.config_entry.async_on_unload(
            async_register_callback(
                self.hass,
                self._async_handle_advertisement,
                BluetoothCallbackMatcher(
                    address=self.toothbrush.address, connectable=True
                ),
                BluetoothScanningMode.PASSIVE,
                replay=BluetoothCallbackReplay.DISABLED,
            )
        )
        async_clear_advertisement_history(self.hass, self.toothbrush.address)

    @callback
    def _async_handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Connect when the toothbrush wakes up and advertises."""
        if self.hass.is_stopping or self.toothbrush.connected:
            return
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), "laifen connect"
        )

    @callback
    def _async_handle_toothbrush_update(self) -> None:
        """Handle a change of the toothbrush or of its connection."""
        if self.hass.is_stopping:
            return
        connected = self.toothbrush.connected
        if connected != self._connected:
            self._connected = connected
            if connected:
                _LOGGER.info("Connected to %s", self.toothbrush.name)
                self.update_interval = UPDATE_INTERVAL
            else:
                _LOGGER.info("%s is asleep or out of range", self.toothbrush.name)
                self.update_interval = None
                async_clear_advertisement_history(self.hass, self.toothbrush.address)
        self._async_update_firmware_version()
        self.async_update_listeners()

    @callback
    def _async_update_firmware_version(self) -> None:
        """Store the firmware version on the device."""
        firmware_version = self.toothbrush.firmware_version
        if firmware_version is None or firmware_version == self._firmware_version:
            return
        self._firmware_version = firmware_version
        dr.async_get(self.hass).async_update_device(
            self.device_id, sw_version=firmware_version
        )

    @override
    async def _async_update_data(self) -> None:
        """Read the state of a connected toothbrush, or connect if it is awake."""
        if self.hass.is_stopping:
            return
        if self.toothbrush.connected:
            try:
                await self.toothbrush.update()
            except LaifenConnectionError as err:
                _LOGGER.debug("Could not update %s: %s", self.toothbrush.name, err)
                await self.toothbrush.disconnect()
            return
        service_info = async_last_service_info(
            self.hass, self.toothbrush.address, connectable=True
        )
        if service_info is None:
            return
        if MONOTONIC_TIME() - service_info.time > ADVERTISEMENT_MAX_AGE:
            async_clear_advertisement_history(self.hass, self.toothbrush.address)
            return
        self.toothbrush.set_ble_device(service_info.device)
        try:
            await self.toothbrush.connect()
        except UnsupportedStateError as err:
            _LOGGER.warning(
                "%s sends a state that is not supported: %s", self.toothbrush.name, err
            )
        except LaifenConnectionError as err:
            _LOGGER.debug(
                "Could not connect to %s: %s (%s)",
                self.toothbrush.name,
                err,
                async_address_reachability_diagnostics(
                    self.hass,
                    self.toothbrush.address,
                    BluetoothReachabilityIntent.CONNECTION,
                ),
            )
            async_clear_advertisement_history(self.hass, self.toothbrush.address)

    @override
    async def async_shutdown(self) -> None:
        """Disconnect from the toothbrush."""
        await super().async_shutdown()
        await self.toothbrush.disconnect()

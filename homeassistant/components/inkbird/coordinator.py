"""The INKBIRD Bluetooth integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from inkbird_ble import INKBIRDBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_DEVICE_TYPE

_LOGGER = logging.getLogger(__name__)

FALLBACK_POLL_INTERVAL = timedelta(seconds=180)


class INKBIRDActiveBluetoothProcessorCoordinator(ActiveBluetoothProcessorCoordinator):
    """Coordinator for INKBIRD Bluetooth devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        data: INKBIRDBluetoothDeviceData,
    ) -> None:
        """Initialize the INKBIRD Bluetooth processor coordinator."""
        self._data = data
        self._entry = entry
        address = entry.unique_id
        assert address is not None
        entry.async_on_unload(
            async_track_time_interval(
                hass, self._async_schedule_poll, FALLBACK_POLL_INTERVAL
            )
        )
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=address,
            mode=BluetoothScanningMode.ACTIVE,
            update_method=self._async_on_update,
            needs_poll_method=self._async_needs_poll,
            poll_method=self._async_poll_data,
        )

    async def _async_poll_data(
        self, last_service_info: BluetoothServiceInfoBleak
    ) -> SensorUpdate:
        """Poll the device."""
        return await self._data.async_poll(last_service_info.device)

    @callback
    def _async_needs_poll(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        return (
            not self.hass.is_stopping
            and self._data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    @callback
    def _async_on_update(self, service_info: BluetoothServiceInfo) -> SensorUpdate:
        """Handle update callback from the passive BLE processor."""
        update = self._data.update(service_info)
        if (
            self._entry.data.get(CONF_DEVICE_TYPE) is None
            and self._data.device_type is not None
        ):
            device_type_str = str(self._data.device_type)
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_DEVICE_TYPE: device_type_str},
            )
        return update

    @callback
    def _async_schedule_poll(self, _: datetime) -> None:
        """Schedule a poll of the device."""
        if self._last_service_info and self._async_needs_poll(
            self._last_service_info, self._last_poll
        ):
            self._debounced_poll.async_schedule_call()

"""Coordinator for the Casper Glow integration."""

from __future__ import annotations

import logging

from bleak import BleakError
from bluetooth_data_tools import monotonic_time_coarse
from pycasperglow import CasperGlow

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import STATE_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

type CasperGlowConfigEntry = ConfigEntry[CasperGlowCoordinator]


class CasperGlowCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):
    """Coordinator for Casper Glow BLE devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: CasperGlow,
        title: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=device.address,
            mode=BluetoothScanningMode.PASSIVE,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_update,
            connectable=True,
        )
        self.device = device
        self.last_dimming_time_minutes: int | None = (
            device.state.configured_dimming_time_minutes
        )
        self.title = title

    @callback
    def _needs_poll(
        self,
        service_info: BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        """Return True if a poll is needed."""
        return (
            seconds_since_last_poll is None
            or seconds_since_last_poll >= STATE_POLL_INTERVAL.total_seconds()
        )

    async def _async_update(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Poll device state."""
        await self.device.query_state()

    async def _async_poll(self) -> None:
        """Poll the device and log availability changes."""
        assert self._last_service_info

        try:
            await self._async_poll_data(self._last_service_info)
        except BleakError as exc:
            if self.last_poll_successful:
                _LOGGER.info("%s is unavailable: %s", self.title, exc)
                self.last_poll_successful = False
            return
        except Exception:
            if self.last_poll_successful:
                _LOGGER.exception("%s: unexpected error while polling", self.title)
                self.last_poll_successful = False
            return
        finally:
            self._last_poll = monotonic_time_coarse()

        if not self.last_poll_successful:
            _LOGGER.info("%s is back online", self.title)
            self.last_poll_successful = True

        self._async_handle_bluetooth_poll()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Update BLE device reference on each advertisement."""
        self.device.set_ble_device(service_info.device)
        super()._async_handle_bluetooth_event(service_info, change)

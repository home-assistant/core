"""Coordinator for the probe_plus integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyprobeplus import ProbePlusDevice
from pyprobeplus.exceptions import ProbePlusDeviceNotFound, ProbePlusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

type ProbePlusConfigEntry = ConfigEntry[ProbePlusDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=15)


class ProbePlusDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to manage data updates for a probe device.

    This class handles the communication with Probe Plus devices.

    Data is updated by the device itself.
    """

    config_entry: ProbePlusConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ProbePlusConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ProbePlusDataUpdateCoordinator",
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

        self.device: ProbePlusDevice = ProbePlusDevice(
            address_or_ble_device=entry.data[CONF_ADDRESS],
            name=entry.title,
            notify_callback=self.async_update_listeners,
        )

    async def _async_update_data(self) -> None:
        """Connect to the Probe Plus device on a set interval.

        This method is called periodically to reconnect to the device
        Data updates are handled by the device itself.
        """
        # Already connected, no need to update any data as the device streams this.
        if self.device.connected:
            return

        # Probe is not connected, try to connect
        try:
            await self.device.connect()
        except (ProbePlusError, ProbePlusDeviceNotFound, TimeoutError) as e:
            _LOGGER.debug(
                "Could not connect to scale: %s, Error: %s",
                self.config_entry.data[CONF_ADDRESS],
                e,
            )
            self.device.device_disconnected_handler(notify=False)
            return

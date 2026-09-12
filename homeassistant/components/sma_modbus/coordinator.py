"""DataUpdateCoordinator that polls an SMA device."""

import logging
from typing import override

from modbus_connection import ModbusError
from sma_modbus import DeviceType, SmaComponent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type SmaCoordinatorConfigEntry = ConfigEntry[SmaCoordinator]


class SmaCoordinator(DataUpdateCoordinator[SmaComponent]):
    """Poll an SMA device through its Modbus unit."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SmaCoordinatorConfigEntry,
        device: SmaComponent,
        device_type: DeviceType,
    ) -> None:
        """Initialize the SMA coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device
        self.device_type = device_type
        self._was_available = False

    @override
    async def _async_update_data(self) -> SmaComponent:
        """Refresh all SMA data."""
        try:
            await self.device.async_update()
        except ModbusError as err:
            if self._was_available:
                _LOGGER.warning(
                    "SMA device at %s became unavailable: %s",
                    self.config_entry.data.get(CONF_HOST),  # type: ignore[union-attr]
                    err,
                )
                self._was_available = False
            raise UpdateFailed(f"Error communicating with SMA device: {err}") from err
        if not self._was_available:
            _LOGGER.info(
                "SMA device at %s is now available",
                self.config_entry.data.get(CONF_HOST),  # type: ignore[union-attr]
            )
            self._was_available = True
        return self.device

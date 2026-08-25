"""Data coordinator for the Flexit integration."""

from datetime import timedelta
import logging
from typing import override

from flexit_modbus import Flexit
from modbus_connection import ModbusError, ModbusUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)

type FlexitConfigEntry = ConfigEntry[FlexitDataCoordinator]


class FlexitDataCoordinator(DataUpdateCoordinator[None]):
    """Data coordinator for a Flexit AC unit."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FlexitConfigEntry,
        unit: ModbusUnit,
    ) -> None:
        """Initialize the FlexitDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Flexit",
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            # The coordinator holds no data of its own (the device object caches
            # the register values), so there is nothing to diff against.
            always_update=True,
        )
        self.device = Flexit(unit)
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=self.name,
            model=self.device.info.model,
            manufacturer=self.device.info.manufacturer,
        )

    @override
    async def _async_update_data(self) -> None:
        """Fetch the latest data from the device."""
        try:
            await self.device.async_update()
        except ModbusError as exception:
            raise UpdateFailed(exception) from exception

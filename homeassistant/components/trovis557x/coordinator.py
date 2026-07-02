"""DataUpdateCoordinator that polls the Trovis controller."""

import logging

from modbus_connection import ModbusError
from trovis_modbus import Trovis557x

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type TrovisConfigEntry = ConfigEntry[TrovisCoordinator]


class TrovisCoordinator(DataUpdateCoordinator[Trovis557x]):
    """Refreshes every sub-system on a schedule.

    ``async_update`` fans out to each component (each reads only its own
    registers), so adding/removing entities never changes what is polled. The
    ``modbus_connection`` entry owns the connection; this coordinator only reads.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TrovisConfigEntry,
        device: Trovis557x,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    async def _async_update_data(self) -> Trovis557x:
        try:
            await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(f"Error communicating with Trovis: {err}") from err
        return self.device

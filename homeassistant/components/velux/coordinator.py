"""DataUpdateCoordinator for Velux limitation data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pyvlx import PyVLXException
from pyvlx.opening_device import OpeningDevice, Position

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

SCAN_INTERVAL = timedelta(minutes=5)


@dataclass
class VeluxLimitationData:
    """Data for one opening device's limitations."""

    limitation_min: Position
    limitation_max: Position


class VeluxLimitationCoordinator(DataUpdateCoordinator[VeluxLimitationData]):
    """Coordinator that fetches limitation min+max for one opening device."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        node: OpeningDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Velux limitation {node.name or f'#{node.node_id}'}",
            update_interval=SCAN_INTERVAL,
        )
        self.node = node

    async def _async_update_data(self) -> VeluxLimitationData:
        """Fetch limitation min and max from the device."""
        try:
            min_pos = await self.node.get_limitation_min()
            max_pos = await self.node.get_limitation_max()
        except (OSError, PyVLXException) as err:
            raise UpdateFailed(f"Error fetching limitations: {err}") from err
        return VeluxLimitationData(limitation_min=min_pos, limitation_max=max_pos)

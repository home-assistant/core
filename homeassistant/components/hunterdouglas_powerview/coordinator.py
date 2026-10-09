"""Coordinate data for powerview devices."""

import asyncio
from datetime import timedelta
import logging
from typing import override, TYPE_CHECKING

from aiopvapi.helpers.aiorequest import PvApiMaintenance
from aiopvapi.hub import Hub
from aiopvapi.resources.shade_data import PowerviewShadeData
from aiopvapi.shades import Shades

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import HUB_EXCEPTIONS, DOMAIN

if TYPE_CHECKING:
    from .model import PowerviewConfigEntry

_LOGGER = logging.getLogger(__name__)


class PowerviewShadeUpdateCoordinator(DataUpdateCoordinator[PowerviewShadeData]):
    """DataUpdateCoordinator to gather data from a powerview hub."""

    config_entry: PowerviewConfigEntry

    def __init__(
        self, 
        hass: HomeAssistant, 
        config_entry: PowerviewConfigEntry, 
        shades: Shades, 
        hub: Hub
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific Hub."""
        self.shades = shades
        self.hub = hub

        # Add tracking of known shades
        self._previous_shade_ids: set[int] = set()
        
        # The hub tends to crash if there are multiple radio operations at the same time
        # but it seems to handle all other requests that do not use RF without issue
        # so we have a lock to prevent multiple radio operations at the same time
        self.radio_operation_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"powerview hub {hub.hub_address}",
            update_interval=timedelta(seconds=60),
        )

    @override
    async def _async_update_data(self) -> PowerviewShadeData:
        """Fetch data from shade endpoint."""

        try:
            shade_entries = await self.shades.get_shades()
        except PvApiMaintenance as error:
            # hub is undergoing maintenance, pause polling
            raise UpdateFailed(error) from error
        except HUB_EXCEPTIONS as error:
            raise UpdateFailed(
                f"Powerview Hub {self.hub.hub_address} did not return any data: {error}"
            ) from error

        if not shade_entries:
            raise UpdateFailed("No new shade data was returned")

        # only update if shade_entries is valid
        self.data.store_group_data(shade_entries)

        # Clean up stale devices
        current_shade_ids = set(self.data.shades.keys())
        
        # Pull all currently tracked HA devices for this integration to check against
        device_registry = dr.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        )
        
        # Audit registry devices to catch phantoms
        for device in devices:
            # Only include shades, don't include the hub device
            if device.via_device_id is not None:
                for identifier in device.identifiers:
                    if identifier[0] == DOMAIN and identifier[1] not in current_shade_ids:
                        # Remove the stale shade and write the removal to the log
                        _LOGGER.info(
                            "Removing device for shade %s that no longer exists on hub",
                            identifier[1]
                        )
                        device_registry.async_remove_device(device.id)

        self._previous_shade_ids = current_shade_ids
        return self.data

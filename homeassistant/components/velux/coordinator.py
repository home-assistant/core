"""DataUpdateCoordinator for Velux integration."""

from __future__ import annotations

from dataclasses import dataclass

from pyvlx.const import Velocity

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


@dataclass
class VeluxData:
    """Velux coordinator data."""

    # There can be only one velocity per device,
    # so we use a dictionary of device_info -> velocity to
    # store the current velocity of each device.
    # This allows setting and getting the velocity for each device
    # in the select entity and cover entity respectively.
    velocities: dict[str, Velocity]  # device_info -> velocity_instance


class VeluxDataUpdateCoordinator(DataUpdateCoordinator[VeluxData]):
    """Coordinator for managing Velux velocity settings."""

    # we only need this coordinator to share velocity state across entities,
    # no periodic updates from an API are required

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
        )
        # Initialize with empty velocities dict
        self.data = VeluxData(velocities={})

    async def _async_update_data(self) -> VeluxData:
        """Fetch data from API endpoint - not needed for velocity storage."""
        # Since we're just managing velocity state, return current data
        return self.data

    def set_velocity(self, device_info: str, velocity: Velocity) -> None:
        """Set velocity for a specific device."""
        self.data.velocities[device_info] = velocity
        # Trigger update to notify all listening entities
        self.async_set_updated_data(self.data)

    def get_velocity(self, device_info: str) -> Velocity:
        """Get velocity for a specific device."""
        return self.data.velocities.get(device_info, Velocity.DEFAULT)

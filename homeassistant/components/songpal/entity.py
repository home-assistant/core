"""Base class for all Songpal entities."""

# I would really like this file to be called "base.py" or "base_entity.py", but C7461 hass-enforce-class-module prevents that

import logging
import re

from songpal.containers import Setting

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SongpalCoordinator
from .device import device_info, device_unique_id

_LOGGER = logging.getLogger(__name__)


class SongpalBaseEntity(CoordinatorEntity):
    """Songpal Base Entity Class.

    This provides shared functionality between all Songpal entities.
    """

    coordinator: SongpalCoordinator

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, coordinator: SongpalCoordinator) -> None:
        """Initialise entity."""
        super().__init__(coordinator)
        self.hass = hass

    @callback
    def update_state(self, data) -> None:
        """Process data from coordinator."""

        raise NotImplementedError("Songpal entity failed to override update_state")

    def get_initial_state(self) -> None:
        """Fetch & process data from coordinator when entity is created."""
        self.update_state(self.coordinator.data)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update latest data from coordinator."""
        # This method is called by SongpalCoordinator when a successful update runs.
        self.update_state(self.coordinator.data)
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return device_info(self.coordinator.device_name, self.coordinator.data)
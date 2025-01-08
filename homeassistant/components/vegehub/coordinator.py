"""Coordinator for the Vegetronix VegeHub."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class VegeHubCoordinator(DataUpdateCoordinator):
    """The DataUpdateCoordinator for VegeHub."""

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        """Initialize VegeHub data coordinator."""
        super().__init__(hass, _LOGGER, name=f"{device_id} DataUpdateCoordinator")
        self.device_id = device_id
        self.data = {}

    async def async_update_data(self, new_data):
        """Update the coordinator with new data from the webhook."""
        super().async_set_updated_data(new_data)

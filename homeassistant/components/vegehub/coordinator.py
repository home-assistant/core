"""Coordinator for the Vegetronix VegeHub."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class VegeHubCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The DataUpdateCoordinator for VegeHub."""

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        """Initialize VegeHub data coordinator."""
        super().__init__(hass, _LOGGER, name=f"{device_id} DataUpdateCoordinator")
        self.device_id = device_id

"""Coordinator for the Vegetronix VegeHub."""

from __future__ import annotations

import logging
from typing import Any

from vegehub import VegeHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type VegeHubConfigEntry = ConfigEntry[VegeHub]


class VegeHubCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The DataUpdateCoordinator for VegeHub."""

    config_entry: VegeHubConfigEntry
    vegehub: VegeHub

    def __init__(
        self, hass: HomeAssistant, config_entry: VegeHubConfigEntry, vegehub: VegeHub
    ) -> None:
        """Initialize VegeHub data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{config_entry.unique_id} DataUpdateCoordinator",
            config_entry=config_entry,
        )
        self.vegehub = vegehub
        self.device_id = config_entry.unique_id

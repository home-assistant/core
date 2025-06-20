"""Droplet device data update coordinator object."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .dropletmqtt import Droplet

_LOGGER = logging.getLogger(__name__)


type DropletConfigEntry = ConfigEntry[DropletDataCoordinator]


class DropletDataCoordinator(DataUpdateCoordinator[None]):
    """Droplet device object."""

    config_entry: DropletConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DropletConfigEntry) -> None:
        """Initialize the device."""
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}-{entry.unique_id}"
        )
        self.droplet = Droplet()

    def get_flow_rate(self) -> float:
        """Retrieve Droplet's latest flow rate."""
        return self.droplet.get_flow_rate()

    def get_availability(self) -> bool:
        """Retrieve Droplet's availability status."""
        return self.droplet.get_availability()

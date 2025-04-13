"""Data Updace Coordinator for Portainer."""

from __future__ import annotations

import logging

from pyportainer import Portainer

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PortainerConfigEntry
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PortainerCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Data Update Coordinator for Portainer."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PortainerConfigEntry,
        api: Portainer,
    ) -> None:
        """Initialize the Portainer Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api

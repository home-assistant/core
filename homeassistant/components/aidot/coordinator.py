"""DataUpdateCoordinator for Aidot."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

type AidotConfigEntry = ConfigEntry[AidotCoordinator]


@dataclass
class AidotData:
    """Class for data update."""


class AidotCoordinator(DataUpdateCoordinator[AidotData]):
    """Class to manage fetching Aidot data."""

    config_entry: AidotConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AidotConfigEntry,
    ) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.identifier = config_entry.entry_id

    async def _async_update_data(self) -> AidotData:
        """Update data async."""
        return AidotData()

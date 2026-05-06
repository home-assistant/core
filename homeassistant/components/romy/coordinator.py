"""ROMY coordinator."""

from romy import RomyRobot

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type RomyConfigEntry = ConfigEntry[RomyVacuumCoordinator]


class RomyVacuumCoordinator(DataUpdateCoordinator[None]):
    """ROMY Vacuum Coordinator."""

    config_entry: RomyConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: RomyConfigEntry, romy: RomyRobot
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.romy = romy

    async def _async_update_data(self) -> None:
        """Update ROMY Vacuum Cleaner data."""
        await self.romy.async_update()

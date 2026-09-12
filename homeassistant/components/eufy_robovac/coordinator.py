"""Data update coordinator for Eufy RoboVac."""

from typing import override

from eufy_robovac import RoboVac, RoboVacConnectionError, RoboVacState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type EufyRoboVacConfigEntry = ConfigEntry[EufyRoboVacCoordinator]


class EufyRoboVacCoordinator(DataUpdateCoordinator[RoboVacState]):
    """Coordinate local polling of an Eufy RoboVac."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EufyRoboVacConfigEntry,
        client: RoboVac,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> RoboVacState:
        """Fetch the latest vacuum state."""
        try:
            return await self.client.update()
        except RoboVacConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

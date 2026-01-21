"""Data update coordinator for OpenEVSE."""

from __future__ import annotations

from datetime import timedelta
import logging

from openevsehttp.__main__ import OpenEVSE

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type OpenEVSEConfigEntry = ConfigEntry[OpenEVSEDataUpdateCoordinator]


class OpenEVSEDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching OpenEVSE data."""

    config_entry: OpenEVSEConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenEVSEConfigEntry,
        charger: OpenEVSE,
    ) -> None:
        """Initialize coordinator."""
        self.charger = charger
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from OpenEVSE charger."""
        try:
            await self.charger.update()
        except TimeoutError as error:
            raise UpdateFailed(
                f"Timeout communicating with charger: {error}"
            ) from error

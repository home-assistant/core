"""Data update coordinator for the Dremel 3D Printer integration."""

from datetime import timedelta

from dremel3dpy import Dremel3DPrinter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type DremelConfigEntry = ConfigEntry[Dremel3DPrinterDataUpdateCoordinator]


class Dremel3DPrinterDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Dremel 3D Printer data."""

    config_entry: DremelConfigEntry

    def __init__(self, hass: HomeAssistant, api: Dremel3DPrinter) -> None:
        """Initialize Dremel 3D Printer data update coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.api = api

    async def _async_update_data(self) -> None:
        """Update data via APIs."""
        try:
            await self.hass.async_add_executor_job(self.api.refresh)
        except RuntimeError as ex:
            raise UpdateFailed(
                f"Unable to refresh printer information: Printer offline: {ex}"
            ) from ex

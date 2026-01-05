"""Data update coordinator for the Skybell integration."""

from datetime import timedelta

from aioskybell import SkybellDevice, SkybellException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


class SkybellDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for the Skybell integration."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, device: SkybellDevice
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=device.name,
            update_interval=timedelta(seconds=30),
        )
        self.device = device

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            await self.device.async_update()
        except SkybellException as err:
            raise UpdateFailed(f"Failed to communicate with device: {err}") from err

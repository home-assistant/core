"""Define an object to manage fetching AirGradient data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from airgradient import AirGradientClient, AirGradientError, Config, Measures

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

if TYPE_CHECKING:
    from . import AirGradientConfigEntry


@dataclass
class AirGradientData:
    """Class for AirGradient data."""

    measures: Measures
    config: Config


class AirGradientCoordinator(DataUpdateCoordinator[AirGradientData]):
    """Class to manage fetching AirGradient data."""

    config_entry: AirGradientConfigEntry

    def __init__(self, hass: HomeAssistant, client: AirGradientClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"AirGradient {client.host}",
            update_interval=timedelta(minutes=1),
        )
        self.client = client
        assert self.config_entry.unique_id
        self.serial_number = self.config_entry.unique_id

    async def _async_update_data(self) -> AirGradientData:
        try:
            measures = await self.client.get_current_measures()
            config = await self.client.get_config()
        except AirGradientError as error:
            raise UpdateFailed(error) from error
        else:
            return AirGradientData(measures, config)

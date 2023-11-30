"""Class representing a Stookwijzer update coordinator."""
from dataclasses import dataclass
from datetime import timedelta
import logging

from stookwijzer import Stookwijzer

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)


class StookwijzerCoordinator(DataUpdateCoordinator[None]):
    """Devialet update coordinator."""

    def __init__(self, hass: HomeAssistant, client: Stookwijzer) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.client.async_update()


@dataclass
class StookwijzerData:
    """Config Entry global data."""

    coordinator: StookwijzerCoordinator | None

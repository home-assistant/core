"""Define an object to coordinate fetching Aladdin Connect data."""

from datetime import timedelta
import logging

from genie_partner_sdk.client import AladdinConnectClient
from genie_partner_sdk.model import GarageDoor

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AladdinConnectCoordinator(DataUpdateCoordinator[None]):
    """Aladdin Connect Data Update Coordinator."""

    doors: list[GarageDoor] | None = None

    def __init__(self, hass: HomeAssistant, acc: AladdinConnectClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self.acc = acc

    async def async_setup(self) -> None:
        """Fetch initial data."""
        self.doors = await self.acc.get_doors()

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        assert self.doors is not None
        for door in self.doors:
            await self.acc.update_door(door.device_id, door.door_number)

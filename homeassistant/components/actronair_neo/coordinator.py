"""Coordinator for Actron Air Neo integration."""

from datetime import timedelta
import logging

from actron_neo_api import ActronNeoAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ActronNeoDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Custom coordinator for Actron Air Neo integration."""

    def __init__(
        self, hass: HomeAssistant, api: ActronNeoAPI, serial_number: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Neo Status",
            update_interval=timedelta(seconds=30),
        )
        self.api = api
        self.serial_number = serial_number
        self.local_state = {"full_update": None, "last_event_id": None}
        self.system = None

    async def _async_update_data(self) -> dict:
        """Fetch updates and merge incremental changes into the full state."""
        if self.system is None:
            self.system = await self.api.get_ac_systems()

        await self.api.get_updated_status(self.serial_number)

        return self.api.status

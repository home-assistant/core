"""Example integration using DataUpdateCoordinator."""

from datetime import timedelta
import logging

from ics_2000.hub import Hub

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import HubConfigEntry

_LOGGER = logging.getLogger(__name__)


class ICS200Coordinator(DataUpdateCoordinator):
    """Coordinator for updating data to and from klikaanklikuit."""

    def __init__(
        self, hass: HomeAssistant, config_entry: HubConfigEntry, hub: Hub
    ) -> None:
        """Initialize the klikaanklikuit coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="KlikAanKlikUit",
            config_entry=config_entry,
            update_interval=timedelta(seconds=2),
            always_update=True,
        )
        self.hub: Hub = hub

    async def _async_update_data(self) -> dict[str, list[int]]:
        await self.hass.async_add_executor_job(self.hub.get_all_device_statuses)
        return {str(k): v for k, v in self.hub.device_statuses.items()}

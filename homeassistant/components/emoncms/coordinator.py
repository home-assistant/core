"""DataUpdateCoordinator for the emoncms integration."""

from datetime import timedelta
from typing import Any

from pyemoncms import EmoncmsClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MESSAGE, CONF_SUCCESS, LOGGER


class EmoncmsCoordinator(DataUpdateCoordinator[list[dict[str, Any]] | None]):
    """Emoncms Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        emoncms_client: EmoncmsClient,
    ) -> None:
        """Initialize the emoncms data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="emoncms_coordinator",
            update_interval=timedelta(seconds=60),
        )
        self.emoncms_client = emoncms_client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API endpoint."""
        data = await self.emoncms_client.async_request("/feed/list.json")
        if not data[CONF_SUCCESS]:
            raise UpdateFailed
        return data[CONF_MESSAGE]

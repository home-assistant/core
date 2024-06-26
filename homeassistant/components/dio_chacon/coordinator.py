"""DataUpdateCoordinator for Dio Chacon integration."""

import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class DioChaconDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to hold Dio Chacon data retrieval and update."""

    def __init__(
        self, hass: HomeAssistant, dio_chacon_client: DIOChaconAPIClient
    ) -> None:
        """Initialize."""

        self.dio_chacon_client = dio_chacon_client

        self.list_devices: dict[str, Any] = {}

        super().__init__(
            hass,
            _LOGGER,
            name="Dio Chacon data coordinator",
        )

    async def async_shutdown(self) -> None:
        """Shutdown the DIO Chacon data update coordinator."""

        # Disconnects the permanent websocket connection of home assistant on shutdown
        await self.dio_chacon_client.disconnect()
        return await super().async_shutdown()

    async def async_config_entry_first_refresh(self) -> None:
        """Initialize the data structure with the devices found via the client api."""

        found_devices = await self.dio_chacon_client.search_all_devices(with_state=True)
        self.list_devices = found_devices.values()
        _LOGGER.debug("List of devices %s", self.list_devices)

    async def _async_update_data(self):
        """Fetch data from API endpoint."""

        # Not used.

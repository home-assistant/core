"""DataUpdateCoordinator for Dio Chacon integration."""

import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class DioChaconDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to hold Dio Chacon data retrieval and update."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""

        config = entry.data

        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]
        dio_chacon_id = config[CONF_UNIQUE_ID]

        def callback_device_state(data: dict[str, Any]) -> None:
            """Receive callback for device state notification pushed from the server."""

            _LOGGER.debug("Data received from server %s", data)
            self.async_set_updated_data(data)

        self.dio_chacon_client: DIOChaconAPIClient = DIOChaconAPIClient(
            username,
            password,
            dio_chacon_id,
        )
        # Register callback for device state notification pushed from the server
        self.dio_chacon_client.set_callback_device_state(callback_device_state)

        self.list_devices: dict[str, Any] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=f"Dio Chacon data coordinator for {dio_chacon_id} = {username}",
        )

    async def async_shutdown(self) -> None:
        """Shutdown the DIO Chacon data update coordinator."""

        # Disconnects the permanent websocket connection of home assistant on shutdown
        await self.dio_chacon_client.disconnect()
        return await super().async_shutdown()

    async def _async_update_data(self):
        """Fetch data from API endpoint."""

        _LOGGER.debug("Updating DIO Chacon data via update coordinator")

        found_devices = await self.dio_chacon_client.search_all_devices(with_state=True)

        self.list_devices = found_devices.values()

        _LOGGER.debug("List of devices %s", self.list_devices)

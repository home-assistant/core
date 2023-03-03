"""UPnP/IGD coordinator."""

from datetime import timedelta
from typing import Any

from async_upnp_client.exceptions import UpnpCommunicationError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER
from .device import Device


class UpnpDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to update data from UPNP device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Device,
        device_entry: DeviceEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.device = device
        self.device_entry = device_entry

        super().__init__(
            hass,
            LOGGER,
            name=device.name,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data."""
        try:
            return await self.device.async_get_data()
        except UpnpCommunicationError as exception:
            LOGGER.debug(
                "Caught exception when updating device: %s, exception: %s",
                self.device,
                exception,
            )
            raise UpdateFailed(
                f"Unable to communicate with IGD at: {self.device.device_url}"
            ) from exception

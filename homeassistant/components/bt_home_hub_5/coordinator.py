"""DataUpdateCoordinator for BT Home Hub 5."""

import logging
from typing import override

from bthomehub5_devicelist import get_devicelist
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type BTHomeHub5ConfigEntry = ConfigEntry[BTHomeHub5DataUpdateCoordinator]


class BTHomeHub5DataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinator to manage fetching BT Home Hub 5 device data."""

    config_entry: BTHomeHub5ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BTHomeHub5ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.host = entry.data[CONF_HOST]

    @override
    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the device list from the router."""
        try:
            data = await self.hass.async_add_executor_job(get_devicelist, self.host)
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(
                f"Error communicating with BT Home Hub 5 at {self.host}: {err}"
            ) from err
        except IndexError as err:
            raise UpdateFailed(
                f"Unexpected response from BT Home Hub 5 at {self.host}"
            ) from err

        if data is None:
            raise UpdateFailed(
                f"Failed to retrieve device list from BT Home Hub 5 at {self.host}"
            )

        return data

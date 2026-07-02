"""Coordinator for Gold Coast Bin Collection."""

import datetime

from gcbinspy.gcbinspy import AddressException, GoldCoastBins
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PROPERTY_ID, DOMAIN, LOGGER

type GCBinCollectionConfigEntry = ConfigEntry[GCBinCollectionCoordinator]

UPDATE_INTERVAL = datetime.timedelta(hours=12)


class GCBinCollectionCoordinator(DataUpdateCoordinator[dict[str, datetime.date]]):
    """Class to manage fetching Gold Coast Bin Collection data."""

    config_entry: GCBinCollectionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GCBinCollectionConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = GoldCoastBins(propertyid=config_entry.data[CONF_PROPERTY_ID])

    def _fetch_data(self) -> dict[str, datetime.date]:
        """Fetch bin collection data from the API (blocking)."""
        self.client.update_next_bin_days()
        return {
            "landfill": self.client.next_landfill(),
            "recycling": self.client.next_recycling(),
            "organics": self.client.next_organics(),
        }

    async def _async_update_data(self) -> dict[str, datetime.date]:
        """Fetch data from the Gold Coast bin collection API."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except AddressException as err:
            raise UpdateFailed(f"Invalid property ID: {err}") from err
        except requests.exceptions.ConnectionError as err:
            raise UpdateFailed(f"Error connecting to API: {err}") from err
        except requests.exceptions.Timeout as err:
            raise UpdateFailed(f"Timeout connecting to API: {err}") from err
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

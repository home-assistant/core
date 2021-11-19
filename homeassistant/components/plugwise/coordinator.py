"""Provides the Plugwise DataUpdateCoordinator."""
import logging

from async_timeout import timeout

from plugwise.exceptions import PlugwiseException, XMLDataMissingError

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class PWDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Plugwise API data from a single endpoint."""

    def __init__(self, hass, api, interval):
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=f"{api.smile_name}", update_interval=interval
        )
        self._api = api
        self._data = {}
        self._u_interval = interval

    async def _async_update_data(self):
        """Update data via API endpoint."""
        try:
            with timeout(self._u_interval.seconds):
                self._data = await self._api.async_update()
                _LOGGER.debug("Plugwise %s updated", self._api.smile_name)
        except XMLDataMissingError as err:
            raise UpdateFailed("Updating failed, no XML data received from Plugwise %s", self._api.smile_name) from err
        except PlugwiseException as err:
            raise UpdateFailed("Updating failed for Plugwise %s", self._api.smile_name) from err
        return self._data

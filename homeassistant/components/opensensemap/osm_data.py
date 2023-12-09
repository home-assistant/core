"""OpenSenseMapData Wrapper."""

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.util import Throttle

from .const import LOGGER, SCAN_INTERVAL


class OpenSenseMapData:
    """Get the latest data and update the states."""

    def __init__(self, api: OpenSenseMap) -> None:
        """Initialize the data object."""
        self.api = api

    @Throttle(SCAN_INTERVAL)
    async def async_update(self) -> None:
        """Receive data from openSenseMap."""

        try:
            await self.api.get_data()
        except OpenSenseMapError as err:
            LOGGER.error("Unable to fetch data: %s", err)

"""Coordinator for the Environment Canada (EC) component."""

from datetime import timedelta
import logging
import xml.etree.ElementTree as et

from env_canada import ec_exc

from homeassistant.const import Platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

DEFAULT_RADAR_UPDATE_INTERVAL = timedelta(minutes=5)
DEFAULT_WEATHER_UPDATE_INTERVAL = timedelta(minutes=5)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR, Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)


class ECDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching EC data."""

    def __init__(self, hass, ec_data, name, update_interval):
        """Initialize global EC data updater."""
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN} {name}", update_interval=update_interval
        )
        self.ec_data = ec_data
        self.last_update_success = False

    async def _async_update_data(self):
        """Fetch data from EC."""
        try:
            await self.ec_data.update()
        except (et.ParseError, ec_exc.UnknownStationId) as ex:
            raise UpdateFailed(f"Error fetching {self.name} data: {ex}") from ex
        return self.ec_data

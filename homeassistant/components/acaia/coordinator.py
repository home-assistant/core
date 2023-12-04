"""Coordinator for Acaia integration."""
from datetime import timedelta
import logging

from pyacaia_async.exceptions import AcaiaError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .acaiaclient import AcaiaClient

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


class AcaiaApiCoordinator(DataUpdateCoordinator[AcaiaClient]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Acaia API coordinator",
            update_interval=SCAN_INTERVAL,
        )

        self._acaia_client: AcaiaClient = AcaiaClient(
            hass=hass,
            entry=config_entry,
            notify_callback=self.async_update_listeners,
        )
        self.data = self._acaia_client

    async def _async_update_data(self) -> AcaiaClient:
        """Fetch data."""
        try:
            await self._acaia_client.async_update()
        except (AcaiaError, TimeoutError) as ex:
            raise UpdateFailed("Error: %s" % ex) from ex

        return self._acaia_client

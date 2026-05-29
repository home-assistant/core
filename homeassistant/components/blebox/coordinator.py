"""DataUpdateCoordinator for BleBox devices."""

from datetime import timedelta
import logging

from blebox_uniapi.box import Box
from blebox_uniapi.error import Error

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BleBoxCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for a single BleBox device."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, box: Box
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self._box = box

    @property
    def box(self) -> Box:
        """Return the BleBox device."""
        return self._box

    async def _async_update_data(self) -> None:
        """Fetch data from the BleBox device."""
        try:
            await self.box.async_update_data()
        except Error as err:
            raise UpdateFailed(str(err)) from err

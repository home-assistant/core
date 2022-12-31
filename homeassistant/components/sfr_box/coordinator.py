"""SFR Box coordinator."""
from datetime import timedelta
import logging

from sfrbox_api.bridge import SFRBox
from sfrbox_api.models import DslInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_SCAN_INTERVAL = timedelta(minutes=1)


class DslDataUpdateCoordinator(DataUpdateCoordinator[DslInfo]):
    """Coordinator to manage data updates."""

    def __init__(self, hass: HomeAssistant, box: SFRBox) -> None:
        """Initialize coordinator."""
        self._box = box
        super().__init__(hass, _LOGGER, name="dsl", update_interval=_SCAN_INTERVAL)

    async def _async_update_data(self) -> DslInfo:
        """Update data."""
        return await self._box.dsl_get_info()

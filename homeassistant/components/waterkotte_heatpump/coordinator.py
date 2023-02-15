"""DataUpdateCoordinator for Waterkotte heatpumps."""
from datetime import timedelta
import logging
from typing import Any

from pywaterkotte.ecotouch import Ecotouch, TagData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EcotouchCoordinator(DataUpdateCoordinator[dict[TagData, Any]]):
    """heatpump coordinator."""

    def __init__(self, heatpump: Ecotouch, hass: HomeAssistant) -> None:
        """Init coordinator."""
        self._heatpump = heatpump

        self.alltags: set[TagData] = set()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[TagData, Any]:
        """Fetch the latest data from the source."""
        tag_list = list(self.alltags)
        return await self.hass.async_add_executor_job(
            self._heatpump.read_values, tag_list
        )

    def get_tag_value(self, tag: TagData) -> StateType:
        """Return a tag value."""
        return self.data.get(tag, None)

    @property
    def heatpump(self) -> Ecotouch:
        """Heatpump api."""
        return self._heatpump

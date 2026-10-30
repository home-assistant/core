"""Component to embed nexia devices."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from nexia.home import NexiaHome

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from .types import NexiaConfigEntry

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_RATE = 120


class NexiaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator for nexia homes."""

    config_entry: NexiaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NexiaConfigEntry,
        nexia_home: NexiaHome,
    ) -> None:
        """Initialize DataUpdateCoordinator for the nexia home."""
        self.nexia_home = nexia_home
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Nexia update",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_RATE),
            always_update=False,
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        update_data = await self.nexia_home.update()  # can return None

        return update_data or {}

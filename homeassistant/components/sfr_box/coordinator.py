"""SFR Box coordinator."""
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any, TypeVar

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
_SCAN_INTERVAL = timedelta(minutes=1)

_T = TypeVar("_T")


class SFRDataUpdateCoordinator(DataUpdateCoordinator[_T]):
    """Coordinator to manage data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        box: SFRBox,
        name: str,
        method: Callable[[SFRBox], Coroutine[Any, Any, _T]],
    ) -> None:
        """Initialize coordinator."""
        self.box = box
        self._method = method
        super().__init__(hass, _LOGGER, name=name, update_interval=_SCAN_INTERVAL)

    async def _async_update_data(self) -> _T:
        """Update data."""
        try:
            return await self._method(self.box)
        except SFRBoxError as err:
            raise UpdateFailed() from err

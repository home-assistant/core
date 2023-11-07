"""Update coordinator for the MotionMount."""
import logging
from typing import Any

import motionmount

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MotionMountCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for MotionMount."""

    def __init__(self, hass: HomeAssistant, mm: motionmount.MotionMount) -> None:
        """Initialize the MotionMount coordinator."""
        super().__init__(hass, _LOGGER, name="MotionMount")
        self._mm = mm

    @property
    def mm(self) -> motionmount.MotionMount:
        """Returns the MotionMount."""
        return self._mm

    async def _async_update_data(self) -> dict[str, Any]:
        return {
            "extension": self._mm.extension,
            "turn": self._mm.turn,
            "is_moving": self._mm.is_moving,
            "target_extension": self._mm.target_extension,
            "target_turn": self._mm.target_turn,
            "error_status": self._mm.error_status,
        }

    def motionmount_callback(self) -> None:
        """Update data from updated MotionMount."""
        self.hass.add_job(self.async_refresh)

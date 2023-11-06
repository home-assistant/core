"""Update coordinator for the MotionMount."""
import logging
from typing import Any

import motionmount  # type: ignore[import-untyped]

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MotionMountCoordinator(DataUpdateCoordinator):
    """Coordinator for MotionMount."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the MotionMount coordinator."""
        super().__init__(hass, _LOGGER, name="MotionMount")
        self._mm: motionmount.MotionMount = None

    @property
    def mm(self) -> motionmount.MotionMount:
        """Returns the MotionMount."""
        return self._mm

    @mm.setter
    def mm(self, new_value: motionmount.MotionMount) -> None:
        self._mm = new_value

    async def _async_update_data(self) -> dict[str, Any]:
        return self._get_data_from_motionmount()

    def motionmount_callback(self) -> None:
        """Update data from updated MotionMount."""
        self.async_set_updated_data(self._get_data_from_motionmount())

    def _get_data_from_motionmount(self) -> dict[str, Any]:
        return {
            "extension": self._mm.extension,
            "turn": self._mm.turn,
            "is_moving": self._mm.is_moving,
            "target_extension": self._mm.target_extension,
            "target_turn": self._mm.target_turn,
            "error_status": self._mm.error_status,
        }

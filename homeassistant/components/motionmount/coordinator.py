"""Update coordinator for the MotionMount."""
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MotionMountCoordinator(DataUpdateCoordinator):
    """Coordinator for MotionMount."""

    def __init__(self, hass):
        """Initialize the MotionMount coordinator."""
        super().__init__(hass, _LOGGER, name="MotionMount")
        self._mm = None

    @property
    def mm(self):
        """Returns the MotionMount."""
        return self._mm

    @mm.setter
    def mm(self, new_value):
        self._mm = new_value

    def motionmount_callback(self):
        """Update data from updated MotionMount."""
        self.async_set_updated_data(
            {
                "extension": self._mm.extension,
                "turn": self._mm.turn,
                "is_moving": self._mm.is_moving,
                "target_extension": self._mm.target_extension,
                "target_turn": self._mm.target_turn,
                "error_status": self._mm.error_status,
            }
        )

import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MotionMountCoordinator(DataUpdateCoordinator):
    """Coordinator for MotionMount."""

    def __init__(self, hass):
        super().__init__(hass, _LOGGER, name="MotionMount")
        self.mm = None

    def motionmount_callback(self):
        self.async_set_updated_data(
            {
                "extension": self.mm.extension,
                "turn": self.mm.turn,
                "is_moving": self.mm.is_moving,
                "target_extension": self.mm.target_turn,
                "target_turn": self.mm.target_extension,
                "error_status": self.mm.error_status,
            }
        )

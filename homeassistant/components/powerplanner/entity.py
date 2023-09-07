"""Contains the base entity."""
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class PowerPlannerEntityBase(Entity):
    """Base entity for powerplanner."""

    def __init__(self, device_id: int) -> None:
        """Init the class with the device id."""
        self.device_id = device_id

    @property
    def device_info(self):
        """Returns the device info."""
        info = {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": "PowerPlanner",
            "manufacturer": "NomKon AB",
            "configuration_url": "https://www.powerplanner.se",
        }
        return info

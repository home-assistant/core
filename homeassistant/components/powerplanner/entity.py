"""Contains the base entity."""
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class PowerPlannerEntityBase(Entity):
    """Base entity for powerplanner."""

    @property
    def device_info(self):
        """Returns the device info."""
        info = {
            "identifiers": {(DOMAIN, "POWERPLANNER1337")},
            "name": "PowerPlanner",
            "manufacturer": "NomKon AB",
            "configuration_url": "https://www.powerplanner.se",
        }
        return info

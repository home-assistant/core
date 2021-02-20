"""Platform for sensor integration."""
import logging

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entity for the thermostat in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [SmartTubState(controller.coordinator, spa) for spa in controller.spas]

    async_add_entities(entities)


class SmartTubState(SmartTubEntity):
    """The state of the spa."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "state")

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self.get_spa_status("state").lower()

"""Platform for sensor integration."""
import logging

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor entities for the sensors in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = []
    for spa in controller.spas:
        entities.extend(
            [
                SmartTubSensor(controller.coordinator, spa, "State", "state"),
                SmartTubSensor(
                    controller.coordinator, spa, "Flow Switch", "flowSwitch"
                ),
                SmartTubSensor(controller.coordinator, spa, "Ozone", "ozone"),
                SmartTubSensor(
                    controller.coordinator, spa, "Blowout Cycle", "blowoutCycle"
                ),
                SmartTubSensor(
                    controller.coordinator, spa, "Cleanup Cycle", "cleanupCycle"
                ),
            ]
        )

    async_add_entities(entities)


class SmartTubSensor(SmartTubEntity):
    """Generic and base class for SmartTub sensors."""

    def __init__(self, coordinator, spa, sensor_name, spa_status_key):
        """Initialize the entity."""
        super().__init__(coordinator, spa, sensor_name)
        self._spa_status_key = spa_status_key

    @property
    def _state(self):
        """Retrieve the underlying state from the spa."""
        return self.get_spa_status(self._spa_status_key)

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.lower()

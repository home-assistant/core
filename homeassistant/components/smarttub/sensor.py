"""Platform for sensor integration."""
import logging

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"
ATTR_LAST_UPDATED = "last_updated"
ATTR_MODE = "mode"
ATTR_START_HOUR = "start_hour"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor entities for the sensors in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = []
    for spa in controller.spas:
        entities.extend(
            [
                SmartTubState(controller.coordinator, spa),
                SmartTubFlowSwitch(controller.coordinator, spa),
                SmartTubOzone(controller.coordinator, spa),
                SmartTubBlowoutCycle(controller.coordinator, spa),
                SmartTubCleanupCycle(controller.coordinator, spa),
            ]
        )

    async_add_entities(entities)


class SmartTubSensor(SmartTubEntity):
    """Base class for SmartTub sensors."""

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


class SmartTubState(SmartTubSensor):
    """The state of the spa."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "State", "state")


class SmartTubFlowSwitch(SmartTubSensor):
    """The state of the flow switch."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Flow Switch", "flowSwitch")


class SmartTubOzone(SmartTubSensor):
    """The state of the ozone system."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Ozone", "ozone")


class SmartTubBlowoutCycle(SmartTubSensor):
    """The state of the blowout cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Blowout Cycle", "blowoutCycle")


class SmartTubCleanupCycle(SmartTubSensor):
    """The state of the cleanup cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Cleanup Cycle", "cleanupCycle")

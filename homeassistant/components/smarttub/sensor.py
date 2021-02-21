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
                SmartTubPrimaryFiltrationCycle(controller.coordinator, spa),
                SmartTubSecondaryFiltrationCycle(controller.coordinator, spa),
            ]
        )

    async_add_entities(entities)


class SmartTubSensor(SmartTubEntity):
    """Base class for SmartTub sensors."""

    def __init__(self, coordinator, spa, sensor_name, attr_name):
        """Initialize the entity."""
        super().__init__(coordinator, spa, sensor_name)
        self._attr_name = attr_name

    @property
    def _state(self):
        """Retrieve the underlying state from the spa."""
        return getattr(self.spa_status, self._attr_name)

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


class SmartTubPrimaryFiltrationCycle(SmartTubSensor):
    """The primary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "primary filtration cycle", "primaryFiltration"
        )

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.status.name.lower()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = self._state
        return {
            ATTR_DURATION: state["duration"],
            ATTR_LAST_UPDATED: state["lastUpdated"],
            ATTR_MODE: state["mode"].lower(),
            ATTR_START_HOUR: state["startHour"],
        }


class SmartTubSecondaryFiltrationCycle(SmartTubSensor):
    """The secondary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "Secondary Filtration Cycle", "secondaryFiltration"
        )

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.get("status").lower()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = self._state
        return {
            ATTR_LAST_UPDATED: state["lastUpdated"],
            ATTR_MODE: state["mode"].lower(),
        }

"""Platform for sensor integration."""
from enum import Enum
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
                SmartTubSensor(controller.coordinator, spa, "State", "state"),
                SmartTubSensor(
                    controller.coordinator, spa, "Flow Switch", "flow_switch"
                ),
                SmartTubSensor(controller.coordinator, spa, "Ozone", "ozone"),
                SmartTubSensor(
                    controller.coordinator, spa, "Blowout Cycle", "blowout_cycle"
                ),
                SmartTubSensor(
                    controller.coordinator, spa, "Cleanup Cycle", "cleanup_cycle"
                ),
                SmartTubPrimaryFiltrationCycle(controller.coordinator, spa),
                SmartTubSecondaryFiltrationCycle(controller.coordinator, spa),
            ]
        )

    async_add_entities(entities)


class SmartTubSensor(SmartTubEntity):
    """Generic and base class for SmartTub sensors."""

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
        if isinstance(self._state, Enum):
            return self._state.name.lower()
        return self._state.lower()


class SmartTubPrimaryFiltrationCycle(SmartTubSensor):
    """The primary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "primary filtration cycle", "primary_filtration"
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
            ATTR_DURATION: state.duration,
            ATTR_LAST_UPDATED: state.last_updated.isoformat(),
            ATTR_MODE: state.mode.name.lower(),
            ATTR_START_HOUR: state.start_hour,
        }


class SmartTubSecondaryFiltrationCycle(SmartTubSensor):
    """The secondary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "Secondary Filtration Cycle", "secondary_filtration"
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
            ATTR_LAST_UPDATED: state.last_updated.isoformat(),
            ATTR_MODE: state.mode.name.lower(),
        }

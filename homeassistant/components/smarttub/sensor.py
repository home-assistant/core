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
                SmartTubPrimaryFiltration(controller.coordinator, spa),
                SmartTubSecondaryFiltration(controller.coordinator, spa),
            ]
        )

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


class SmartTubFlowSwitch(SmartTubEntity):
    """The state of the flow switch."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "flow_switch")

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self.get_spa_status("flowSwitch").lower()


class SmartTubOzone(SmartTubEntity):
    """The state of the ozone system."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "ozone")

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self.get_spa_status("ozone").lower()


class SmartTubBlowoutCycle(SmartTubEntity):
    """The state of the blowout cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "blowout_cycle")

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self.get_spa_status("blowoutCycle").lower()


class SmartTubCleanupCycle(SmartTubEntity):
    """The state of the cleanup cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "cleanup_cycle")

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self.get_spa_status("cleanupCycle").lower()


class SmartTubPrimaryFiltration(SmartTubEntity):
    """The primary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "primary_filtration")

    @property
    def _state(self):
        return self.get_spa_status("primaryFiltration")

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.get("status").lower()

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


class SmartTubSecondaryFiltration(SmartTubEntity):
    """The secondary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "secondary_filtration")

    @property
    def _state(self):
        return self.get_spa_status("secondaryFiltration")

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

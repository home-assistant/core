"""Support for Litter-Robot sensors."""
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import LitterRobotEntity

WASTE_DRAWER = "Waste Drawer"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Litter-Robot sensors using config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for robot in hub.account.robots:
        entities.append(LitterRobotSensor(robot, WASTE_DRAWER, hub))

    if entities:
        async_add_entities(entities, True)


class LitterRobotSensor(LitterRobotEntity, Entity):
    """Litter-Robot sensors."""

    @property
    def state(self):
        """Return the state."""
        return self.robot.waste_drawer_gauge

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self.robot.waste_drawer_gauge <= 10:
            return "mdi:gauge-empty"
        if self.robot.waste_drawer_gauge < 50:
            return "mdi:gauge-low"
        if self.robot.waste_drawer_gauge <= 90:
            return "mdi:gauge"
        return "mdi:gauge-full"

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "cycle_count": self.robot.cycle_count,
            "cycle_capacity": self.robot.cycle_capacity,
            "cycles_after_drawer_full": self.robot.cycles_after_drawer_full,
        }

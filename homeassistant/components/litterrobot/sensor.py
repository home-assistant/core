"""Support for Litter-Robot sensors."""
from __future__ import annotations

from pylitterbot.robot import Robot

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TIMESTAMP, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity
from .hub import LitterRobotHub


def icon_for_gauge_level(gauge_level: int | None = None, offset: int = 0) -> str:
    """Return a gauge icon valid identifier."""
    if gauge_level is None or gauge_level <= 0 + offset:
        return "mdi:gauge-empty"
    if gauge_level > 70 + offset:
        return "mdi:gauge-full"
    if gauge_level > 30 + offset:
        return "mdi:gauge"
    return "mdi:gauge-low"


class LitterRobotPropertySensor(LitterRobotEntity, SensorEntity):
    """Litter-Robot property sensor."""

    def __init__(
        self, robot: Robot, entity_type: str, hub: LitterRobotHub, sensor_attribute: str
    ) -> None:
        """Pass robot, entity_type and hub to LitterRobotEntity."""
        super().__init__(robot, entity_type, hub)
        self.sensor_attribute = sensor_attribute

    @property
    def state(self) -> str:
        """Return the state."""
        return getattr(self.robot, self.sensor_attribute)


class LitterRobotWasteSensor(LitterRobotPropertySensor):
    """Litter-Robot waste sensor."""

    @property
    def unit_of_measurement(self) -> str:
        """Return unit of measurement."""
        return PERCENTAGE

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return icon_for_gauge_level(self.state, 10)


class LitterRobotSleepTimeSensor(LitterRobotPropertySensor):
    """Litter-Robot sleep time sensor."""

    @property
    def state(self) -> str | None:
        """Return the state."""
        if self.robot.sleep_mode_enabled:
            return super().state.isoformat()
        return None

    @property
    def device_class(self) -> str:
        """Return the device class, if any."""
        return DEVICE_CLASS_TIMESTAMP


ROBOT_SENSORS: list[tuple[type[LitterRobotPropertySensor], str, str]] = [
    (LitterRobotWasteSensor, "Waste Drawer", "waste_drawer_level"),
    (LitterRobotSleepTimeSensor, "Sleep Mode Start Time", "sleep_mode_start_time"),
    (LitterRobotSleepTimeSensor, "Sleep Mode End Time", "sleep_mode_end_time"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot sensors using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for robot in hub.account.robots:
        for (sensor_class, entity_type, sensor_attribute) in ROBOT_SENSORS:
            entities.append(
                sensor_class(
                    robot=robot,
                    entity_type=entity_type,
                    hub=hub,
                    sensor_attribute=sensor_attribute,
                )
            )

    async_add_entities(entities, True)

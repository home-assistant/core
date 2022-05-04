"""Support for Litter-Robot binary sensors."""
from pylitterbot.enums import LitterBoxStatus

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity
from .hub import LitterRobotHub


class LitterRobotBinarySensor(LitterRobotEntity, BinarySensorEntity):
    """Litter-Robot binary sensor."""


class LitterRobotTimingModeSensor(LitterRobotBinarySensor):
    """Litter-Robot timing mode sensor."""

    @property
    def is_on(self) -> bool:
        """If the binary sensor is currently on or off."""
        return self.robot.status == LitterBoxStatus.CAT_SENSOR_TIMING

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:timer-outline" if self.is_on else "mdi:timer-off-outline"


ROBOT_BINARY_SENSORS: list[tuple[type[LitterRobotBinarySensor], str]] = [
    (LitterRobotTimingModeSensor, "Timing Mode"),
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
        for (sensor_class, entity_type) in ROBOT_BINARY_SENSORS:
            entities.append(sensor_class(robot=robot, entity_type=entity_type, hub=hub))

    async_add_entities(entities)

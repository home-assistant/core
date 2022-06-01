"""Support for Litter-Robot sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pylitterbot.robot import Robot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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


@dataclass
class LitterRobotSensorEntityDescription(SensorEntityDescription):
    """A class that describes Litter-Robot sensor entities."""

    icon_fn: Callable[[Any], str | None] = lambda _: None
    should_report: Callable[[Robot], bool] = lambda _: True


class LitterRobotSensorEntity(LitterRobotEntity, SensorEntity):
    """Litter-Robot sensor entity."""

    entity_description: LitterRobotSensorEntityDescription

    def __init__(
        self,
        robot: Robot,
        hub: LitterRobotHub,
        description: LitterRobotSensorEntityDescription,
    ) -> None:
        """Initialize a Litter-Robot sensor entity."""
        assert description.name
        super().__init__(robot, description.name, hub)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        if self.entity_description.should_report(self.robot):
            if isinstance(val := getattr(self.robot, self.entity_description.key), str):
                return val.lower()
            return val
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon


ROBOT_SENSORS = [
    LitterRobotSensorEntityDescription(
        name="Waste Drawer",
        key="waste_drawer_level",
        native_unit_of_measurement=PERCENTAGE,
        icon_fn=lambda state: icon_for_gauge_level(state, 10),
    ),
    LitterRobotSensorEntityDescription(
        name="Sleep Mode Start Time",
        key="sleep_mode_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        should_report=lambda robot: robot.sleep_mode_enabled,
    ),
    LitterRobotSensorEntityDescription(
        name="Sleep Mode End Time",
        key="sleep_mode_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        should_report=lambda robot: robot.sleep_mode_enabled,
    ),
    LitterRobotSensorEntityDescription(
        name="Last Seen",
        key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LitterRobotSensorEntityDescription(
        name="Status Code",
        key="status_code",
        device_class="litterrobot__status_code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot sensors using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LitterRobotSensorEntity(robot=robot, hub=hub, description=description)
        for description in ROBOT_SENSORS
        for robot in hub.account.robots
    )

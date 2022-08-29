"""Support for Litter-Robot sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Union, cast

from pylitterbot import FeederRobot, LitterRobot, Robot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
class RobotSensorEntityDescription(SensorEntityDescription):
    """A class that describes robot sensor entities."""

    icon_fn: Callable[[Any], str | None] = lambda _: None
    should_report: Callable[[Robot], bool] = lambda _: True


@dataclass
class LitterRobotSensorEntityDescription(RobotSensorEntityDescription):
    """A class that describes Litter-Robot sensor entities."""

    should_report: Callable[[LitterRobot], bool] = lambda _: True


class LitterRobotSensorEntity(LitterRobotEntity, SensorEntity):
    """Litter-Robot sensor entity."""

    entity_description: RobotSensorEntityDescription

    def __init__(
        self,
        robot: LitterRobot | FeederRobot,
        hub: LitterRobotHub,
        description: RobotSensorEntityDescription,
    ) -> None:
        """Initialize a Litter-Robot sensor entity."""
        assert description.name
        super().__init__(robot, description.name, hub)
        self.entity_description = description

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""
        if self.entity_description.should_report(self.robot):
            if isinstance(val := getattr(self.robot, self.entity_description.key), str):
                return val.lower()
            return cast(Union[float, datetime, None], val)
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon


LITTER_ROBOT_SENSORS = [
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

FEEDER_ROBOT_SENSOR = RobotSensorEntityDescription(
    name="Food Level",
    key="food_level",
    native_unit_of_measurement=PERCENTAGE,
    icon_fn=lambda state: icon_for_gauge_level(state, 10),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot sensors using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LitterRobotSensorEntity(robot=robot, hub=hub, description=description)
            for description in LITTER_ROBOT_SENSORS
            for robot in hub.litter_robots()
        ]
        + [
            LitterRobotSensorEntity(
                robot=robot, hub=hub, description=FEEDER_ROBOT_SENSOR
            )
            for robot in hub.feeder_robots()
        ]
    )

"""Support for Litter-Robot sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, cast

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, Robot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _RobotT


def icon_for_gauge_level(gauge_level: int | None = None, offset: int = 0) -> str:
    """Return a gauge icon valid identifier."""
    if gauge_level is None or gauge_level <= 0 + offset:
        return "mdi:gauge-empty"
    if gauge_level > 70 + offset:
        return "mdi:gauge-full"
    if gauge_level > 30 + offset:
        return "mdi:gauge"
    return "mdi:gauge-low"


@dataclass(frozen=True)
class RobotSensorEntityDescription(SensorEntityDescription, Generic[_RobotT]):
    """A class that describes robot sensor entities."""

    icon_fn: Callable[[Any], str | None] = lambda _: None
    should_report: Callable[[_RobotT], bool] = lambda _: True


class LitterRobotSensorEntity(LitterRobotEntity[_RobotT], SensorEntity):
    """Litter-Robot sensor entity."""

    entity_description: RobotSensorEntityDescription[_RobotT]

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""
        if self.entity_description.should_report(self.robot):
            if isinstance(val := getattr(self.robot, self.entity_description.key), str):
                return val.lower()
            return cast(float | datetime | None, val)
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon


ROBOT_SENSOR_MAP: dict[type[Robot], list[RobotSensorEntityDescription]] = {
    LitterRobot: [  # type: ignore[type-abstract]  # only used for isinstance check
        RobotSensorEntityDescription[LitterRobot](
            key="waste_drawer_level",
            translation_key="waste_drawer",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_start_time",
            translation_key="sleep_mode_start_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            should_report=lambda robot: robot.sleep_mode_enabled,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_end_time",
            translation_key="sleep_mode_end_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            should_report=lambda robot: robot.sleep_mode_enabled,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="last_seen",
            translation_key="last_seen",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="status_code",
            translation_key="status_code",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
            options=[
                "br",
                "ccc",
                "ccp",
                "cd",
                "csf",
                "csi",
                "cst",
                "df1",
                "df2",
                "dfs",
                "dhf",
                "dpf",
                "ec",
                "hpf",
                "off",
                "offline",
                "otf",
                "p",
                "pd",
                "pwrd",
                "pwru",
                "rdy",
                "scf",
                "sdf",
                "spf",
            ],
        ),
    ],
    LitterRobot4: [
        RobotSensorEntityDescription[LitterRobot4](
            key="litter_level",
            translation_key="litter_level",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
        ),
        RobotSensorEntityDescription[LitterRobot4](
            key="pet_weight",
            translation_key="pet_weight",
            native_unit_of_measurement=UnitOfMass.POUNDS,
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ],
    FeederRobot: [
        RobotSensorEntityDescription[FeederRobot](
            key="food_level",
            translation_key="food_level",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
        )
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot sensors using config entry."""
    hub = entry.runtime_data
    entities = [
        LitterRobotSensorEntity(robot=robot, hub=hub, description=description)
        for robot in hub.account.robots
        for robot_type, entity_descriptions in ROBOT_SENSOR_MAP.items()
        if isinstance(robot, robot_type)
        for description in entity_descriptions
    ]
    async_add_entities(entities)

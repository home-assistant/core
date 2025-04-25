"""Support for Litter-Robot sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, Pet, Robot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _WhiskerEntityT


def icon_for_gauge_level(gauge_level: int | None = None, offset: int = 0) -> str:
    """Return a gauge icon valid identifier."""
    if gauge_level is None or gauge_level <= 0 + offset:
        return "mdi:gauge-empty"
    if gauge_level > 70 + offset:
        return "mdi:gauge-full"
    if gauge_level > 30 + offset:
        return "mdi:gauge"
    return "mdi:gauge-low"


@dataclass(frozen=True, kw_only=True)
class RobotSensorEntityDescription(SensorEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot sensor entities."""

    icon_fn: Callable[[Any], str | None] = lambda _: None
    value_fn: Callable[[_WhiskerEntityT], float | datetime | str | None]


ROBOT_SENSOR_MAP: dict[type[Robot], list[RobotSensorEntityDescription]] = {
    LitterRobot: [  # type: ignore[type-abstract]  # only used for isinstance check
        RobotSensorEntityDescription[LitterRobot](
            key="waste_drawer_level",
            translation_key="waste_drawer",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.waste_drawer_level,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_start_time",
            translation_key="sleep_mode_start_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=(
                lambda robot: (
                    robot.sleep_mode_start_time if robot.sleep_mode_enabled else None
                )
            ),
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_end_time",
            translation_key="sleep_mode_end_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=(
                lambda robot: (
                    robot.sleep_mode_end_time if robot.sleep_mode_enabled else None
                )
            ),
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="last_seen",
            translation_key="last_seen",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda robot: robot.last_seen,
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
            value_fn=(
                lambda robot: status.lower() if (status := robot.status_code) else None
            ),
        ),
    ],
    LitterRobot4: [
        RobotSensorEntityDescription[LitterRobot4](
            key="hopper_status",
            translation_key="hopper_status",
            device_class=SensorDeviceClass.ENUM,
            options=[
                "enabled",
                "disabled",
                "motor_fault_short",
                "motor_ot_amps",
                "motor_disconnected",
                "empty",
            ],
            value_fn=(
                lambda robot: (
                    status.lower() if (status := robot.hopper_status) else None
                )
            ),
        ),
        RobotSensorEntityDescription[LitterRobot4](
            key="litter_level",
            translation_key="litter_level",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.litter_level,
        ),
        RobotSensorEntityDescription[LitterRobot4](
            key="pet_weight",
            translation_key="pet_weight",
            native_unit_of_measurement=UnitOfMass.POUNDS,
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.pet_weight,
        ),
    ],
    FeederRobot: [
        RobotSensorEntityDescription[FeederRobot](
            key="food_level",
            translation_key="food_level",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.food_level,
        )
    ],
}

PET_SENSORS: list[RobotSensorEntityDescription] = [
    RobotSensorEntityDescription[Pet](
        key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pet: pet.weight,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot sensors using config entry."""
    coordinator = entry.runtime_data
    entities: list[LitterRobotSensorEntity] = [
        LitterRobotSensorEntity(
            robot=robot, coordinator=coordinator, description=description
        )
        for robot in coordinator.account.robots
        for robot_type, entity_descriptions in ROBOT_SENSOR_MAP.items()
        if isinstance(robot, robot_type)
        for description in entity_descriptions
    ]
    entities.extend(
        LitterRobotSensorEntity(
            robot=pet, coordinator=coordinator, description=description
        )
        for pet in coordinator.account.pets
        for description in PET_SENSORS
    )
    async_add_entities(entities)


class LitterRobotSensorEntity(LitterRobotEntity[_WhiskerEntityT], SensorEntity):
    """Litter-Robot sensor entity."""

    entity_description: RobotSensorEntityDescription[_WhiskerEntityT]

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""
        return self.entity_description.value_fn(self.robot)

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon
